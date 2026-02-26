#!/usr/bin/env python3
"""
Audiobook Pipeline - Background Job Runner

Handles the complete audiobook generation pipeline:
1. Translation (if needed)
2. Summarization (optional)
3. Audio generation (Kokoro TTS)
4. Cover art generation (optional)
5. Server registration

Features:
- Background job queue with max 2 concurrent jobs
- Resumable (saves state after each stage)
- Real-time progress tracking
- Error recovery
"""

import json
import os
import re
import time
import uuid
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from enum import Enum

from server.language_detector import detect_language
from lib.translation.engine import OllamaTranslator
from lib.translation.structured import (
    BookParser,
    StructureValidator,
    BlockTranslator,
    MarkdownAssembler,
    TranslationConfig,
    translate_book
)


# Constants
BOOKS_DIR = Path(__file__).parent.parent / "books"

# Retry configuration for audio generation subprocess
AUDIO_MAX_RETRIES = 3
AUDIO_RETRY_DELAYS = [5, 15, 30]  # seconds between retries

# Error patterns indicating permanent (non-retryable) failures
PERMANENT_ERROR_PATTERNS = [
    "Input file not found",
    "FileNotFoundError",
    "book_manifest.json not found",
    "Missing dependencies",
    "No handler registered",
    "make_audiobook.py not found",
    "Python interpreter check failed",
    "kokoro-onnx library not installed",
    "Auto-fix failed",
    "summarize must be between",
]

# Exit codes that indicate permanent failure
PERMANENT_EXIT_CODES = {2}  # validation/auto-fix failure


class JobStatus(str, Enum):
    """Job status enum"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelineStage(str, Enum):
    """Pipeline stage enum"""
    QUEUED = "queued"
    LANGUAGE_DETECTION = "language_detection"
    TRANSLATION = "translation"
    SUMMARIZATION = "summarization"
    AUDIO_GENERATION = "audio_generation"
    COVER_ART = "cover_art"
    REGISTRATION = "registration"
    DONE = "done"


class JobState:
    """Represents a pipeline job with state tracking"""

    # Set to False to disable JSON file persistence (when managed by unified queue)
    persist_to_json = True

    def __init__(
        self,
        job_id: str,
        book_id: str,
        source_file: str,
        config: Dict
    ):
        """
        Initialize job state.

        Args:
            job_id: Unique job identifier
            book_id: Book directory name
            source_file: Source markdown filename
            config: Job configuration (voice, speed, translate, summarize, etc.)
        """
        self.job_id = job_id
        self.book_id = book_id
        self.source_file = source_file
        self.config = config

        # State
        self.status = JobStatus.PENDING
        self.current_stage = PipelineStage.QUEUED
        self.progress = 0  # 0-100
        self.stage_progress = {}  # Stage-specific progress info

        # Timing
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at
        self.started_at = None
        self.completed_at = None

        # Results
        self.error = None
        self.output_files = {}  # {stage: file_path}

    def _save_state(self):
        """Save job state to disk (only if JSON persistence is enabled)."""
        if not self.persist_to_json:
            return

    def update(
        self,
        status: Optional[JobStatus] = None,
        stage: Optional[PipelineStage] = None,
        progress: Optional[int] = None,
        stage_progress: Optional[Dict] = None,
        error: Optional[str] = None
    ):
        """Update job state and save"""
        if status:
            self.status = status
            if status == JobStatus.RUNNING and not self.started_at:
                self.started_at = datetime.now().isoformat()
            elif status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                self.completed_at = datetime.now().isoformat()

        if stage:
            self.current_stage = stage

        if progress is not None:
            self.progress = max(0, min(100, progress))

        if stage_progress is not None:
            self.stage_progress = stage_progress

        if error:
            self.error = error

        self.updated_at = datetime.now().isoformat()
        self._save_state()

    def to_dict(self) -> Dict:
        """Convert to dictionary for API response"""
        # Calculate stage-based ETA for more accurate estimates
        eta_seconds = None
        if self.status == JobStatus.RUNNING and self.started_at:
            # Stage-specific time estimates (in seconds)
            stage_estimates = {
                PipelineStage.LANGUAGE_DETECTION: 30,      # 30 seconds
                PipelineStage.TRANSLATION: 3600,           # 60 minutes
                PipelineStage.SUMMARIZATION: 1800,         # 30 minutes
                PipelineStage.AUDIO_GENERATION: 600,       # 10 minutes
                PipelineStage.COVER_ART: 120,              # 2 minutes
                PipelineStage.REGISTRATION: 10             # 10 seconds
            }

            # Calculate remaining time based on current and remaining stages
            if self.current_stage == PipelineStage.AUDIO_GENERATION:
                # For audio generation, use chunk progress if available
                if self.stage_progress and 'total_chunks' in self.stage_progress:
                    current_chunk = self.stage_progress.get('current_chunk', 0)
                    total_chunks = self.stage_progress['total_chunks']
                    if total_chunks > 0 and current_chunk > 0:
                        # Estimate based on average time per chunk
                        elapsed = (datetime.now() - datetime.fromisoformat(self.started_at)).total_seconds()
                        time_per_chunk = elapsed / current_chunk
                        remaining_chunks = total_chunks - current_chunk
                        eta_seconds = max(0, time_per_chunk * remaining_chunks)
                    else:
                        eta_seconds = stage_estimates.get(self.current_stage, 300)
                else:
                    eta_seconds = stage_estimates.get(self.current_stage, 300)
            else:
                # For other stages, use the estimate
                eta_seconds = stage_estimates.get(self.current_stage, 300)

            # Add estimates for remaining stages
            remaining_stages = []
            if self.current_stage != PipelineStage.REGISTRATION:
                if self.current_stage == PipelineStage.AUDIO_GENERATION:
                    if self.config.get('generate_cover'):
                        remaining_stages.append(PipelineStage.COVER_ART)
                    remaining_stages.append(PipelineStage.REGISTRATION)
                elif self.current_stage == PipelineStage.COVER_ART:
                    remaining_stages.append(PipelineStage.REGISTRATION)

            for stage in remaining_stages:
                eta_seconds = (eta_seconds or 0) + stage_estimates.get(stage, 0)

        return {
            'job_id': self.job_id,
            'book_id': self.book_id,
            'source_file': self.source_file,
            'config': self.config,
            'status': self.status,
            'current_stage': self.current_stage,
            'progress': self.progress,
            'stage_progress': self.stage_progress,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'eta_seconds': eta_seconds,
            'error': self.error,
            'output_files': self.output_files
        }


class PipelineRunner:
    """Runs the audiobook generation pipeline"""

    def __init__(self, job: JobState):
        """
        Initialize pipeline runner.

        Args:
            job: Job state to execute
        """
        self.job = job
        self.book_dir = BOOKS_DIR / job.book_id
        self.cancelled = False
        self.progress_map = self._calculate_progress_map()

    def _calculate_progress_map(self):
        """
        Calculate dynamic progress ranges based on enabled stages.

        Returns:
            Dict mapping stage names to (start_pct, end_pct) tuples
        """
        stages = []

        # Add stages based on configuration
        if self.job.config.get('translate'):
            stages.append(('language_detection', 5))   # 5% weight
            stages.append(('translation', 30))          # 30% weight

        if self.job.config.get('summarize'):
            stages.append(('summarization', 20))        # 20% weight

        # Always include these stages
        stages.append(('audio_generation', 40))         # 40% weight (main work)

        if self.job.config.get('generate_cover'):
            stages.append(('cover_art', 3))             # 3% weight

        stages.append(('registration', 2))              # 2% weight

        # Normalize weights to 0-100%
        total_weight = sum(weight for _, weight in stages)
        progress_map = {}
        current = 0

        for stage_name, weight in stages:
            stage_pct = (weight / total_weight) * 100
            progress_map[stage_name] = (current, min(current + stage_pct, 100))
            current = min(current + stage_pct, 100)

        return progress_map

    def _is_permanent_failure(self, exit_code: int, output_lines: list) -> bool:
        """Determine if a subprocess failure is permanent (non-retryable)."""
        if exit_code in PERMANENT_EXIT_CODES:
            return True
        # Check last 50 lines for permanent error patterns
        tail = "\n".join(output_lines[-50:])
        for pattern in PERMANENT_ERROR_PATTERNS:
            if pattern in tail:
                return True
        return False

    def _build_error_message(self, return_code: int, all_output: list, cmd: list) -> str:
        """Build detailed error message from subprocess output."""
        error_lines = all_output[-30:] if len(all_output) > 30 else all_output

        actual_error = None
        for line in reversed(all_output):
            if 'ERROR' in line or 'Error' in line or 'error' in line:
                actual_error = line.strip()
                break

        error_msg = f"Audio generation failed with exit code {return_code}\n\n"
        if actual_error:
            error_msg += f"Error: {actual_error}\n\n"
        error_msg += f"Command: {' '.join(cmd)}\n\n"
        if error_lines:
            error_msg += "Output (last 30 lines):\n"
            error_msg += "\n".join(error_lines)
        else:
            error_msg += "No output captured (process may have crashed immediately)\n"
        error_msg += "\n\nTroubleshooting:\n"
        error_msg += "  - Check that venv is activated: source venv/bin/activate\n"
        error_msg += "  - Verify kokoro-onnx is installed: pip list | grep kokoro\n"
        error_msg += "  - Try running manually: " + ' '.join(cmd)
        return error_msg

    def _execute_audio_subprocess(self, cmd, sub_env, voice, start_pct, end_pct):
        """Execute make_audiobook.py subprocess with progress monitoring.

        Returns:
            Tuple of (return_code, all_output_lines)
        """
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=sub_env
        )

        all_output = []

        for line in iter(process.stdout.readline, ''):
            if self.cancelled:
                process.kill()
                raise Exception("Job cancelled by user")

            all_output.append(line.rstrip())
            print(f"  [audio] {line.rstrip()}", flush=True)

            progress_match = re.search(
                r'(?:\[|Progress:.*?)(\d+)\s*/\s*(\d+)(?:\]|\s|$)',
                line
            )
            if progress_match:
                current = int(progress_match.group(1))
                total = int(progress_match.group(2))
                if 1 <= current <= total and 2 <= total <= 50000:
                    chunk_progress = int((current / total) * 100)
                    progress_range = end_pct - start_pct
                    overall_progress = int(start_pct + (chunk_progress * progress_range / 100))
                    self.job.update(
                        progress=overall_progress,
                        stage_progress={
                            'message': f'Generating audio chunk {current}/{total}...',
                            'current_chunk': current,
                            'total_chunks': total,
                            'voice': voice
                        }
                    )

        process.wait()
        return process.returncode, all_output

    def run(self):
        """Execute the pipeline"""
        try:
            self.job.update(status=JobStatus.RUNNING, progress=0)

            # Stage 1: Language Detection (0-5%)
            if self.job.config.get('translate'):
                self._run_language_detection()

            # Stage 2: Translation (5-35%)
            if self.job.config.get('translate'):
                translated_file = self._run_translation()
            else:
                translated_file = self.book_dir / self.job.source_file

            # Stage 3: Summarization (35-55%)
            if self.job.config.get('summarize'):
                summarized_file = self._run_summarization(translated_file)
            else:
                summarized_file = translated_file

            # Stage 4: Audio Generation (55-95%)
            audio_result = self._run_audio_generation(summarized_file)

            # Stage 5: Cover Art (95-98%)
            if self.job.config.get('generate_cover'):
                self._run_cover_generation(audio_result)

            # Stage 6: Registration (98-100%)
            self._run_registration(audio_result)

            # Complete
            self.job.update(
                status=JobStatus.COMPLETED,
                stage=PipelineStage.DONE,
                progress=100
            )

        except Exception as e:
            self.job.update(
                status=JobStatus.FAILED,
                error=str(e)
            )
            raise

    def _run_language_detection(self):
        """Detect source language"""
        start_pct, end_pct = self.progress_map.get('language_detection', (0, 5))

        self.job.update(
            stage=PipelineStage.LANGUAGE_DETECTION,
            progress=int(start_pct),
            stage_progress={'message': 'Detecting source language...'}
        )

        source_path = self.book_dir / self.job.source_file
        result = detect_language(source_path)

        self.job.config['detected_language'] = result['language']
        self.job.config['language_confidence'] = result['confidence']
        self.job.update(progress=int(end_pct))

    def _run_translation(self) -> Path:
        """
        Run translation using structured translator (NEW - preserves chapter structure).

        Returns:
            Path to translated file
        """
        start_pct, end_pct = self.progress_map.get('translation', (5, 35))

        self.job.update(
            stage=PipelineStage.TRANSLATION,
            progress=int(start_pct),
            stage_progress={'message': 'Validating source book structure...'}
        )

        source_path = self.book_dir / self.job.source_file
        source_lang = self.job.config.get('source_language', 'Russian')
        target_lang = self.job.config.get('target_language', 'Modern English')
        model = self.job.config.get('translation_model', 'zongwei/gemma3-translator:4b')

        # Create translation config for structured translator
        config = TranslationConfig(
            source_lang=source_lang,
            target_lang=target_lang,
            translator_type='ollama',
            model_name=model,
            translate_metadata=True,
            preserve_markers=True
        )

        # Progress callback for chapter-by-chapter tracking
        def progress_callback(current: int, total: int):
            if self.cancelled:
                raise Exception("Job cancelled by user")

            chapter_progress = int((current / total) * 100)
            # Use dynamic progress range from progress_map
            progress_range = end_pct - start_pct
            overall_progress = int(start_pct + (chapter_progress * progress_range / 100))
            self.job.update(
                progress=overall_progress,
                stage_progress={
                    'message': f'Translating chapter {current}/{total}...',
                    'current_chapter': current,
                    'total_chapters': total
                }
            )

        # STEP 1: Parse structure
        self.job.update(stage_progress={'message': 'Parsing book structure...'})
        parser = BookParser()
        structure = parser.parse(source_path)

        # STEP 2: Validate structure (fail-fast if incomplete)
        # Progress at 10% through the translation stage
        validation_progress = int(start_pct + (end_pct - start_pct) * 0.1)
        self.job.update(
            progress=validation_progress,
            stage_progress={'message': f'Validating structure ({len(structure.chapters)} chapters)...'}
        )
        validator = StructureValidator()
        try:
            validation_report = validator.validate(structure)
        except ValueError as e:
            raise Exception(f"Source book validation failed: {e}")

        # STEP 3: Translate blocks
        # Progress at 20% through the translation stage
        translate_start_progress = int(start_pct + (end_pct - start_pct) * 0.2)
        self.job.update(
            progress=translate_start_progress,
            stage_progress={'message': f'Translating {len(structure.chapters)} chapters...'}
        )

        # Create checkpoint file for resumability
        checkpoint_file = self.book_dir / f".translation_checkpoint_{source_path.stem}.json"

        translator = BlockTranslator(config, progress_callback=progress_callback, checkpoint_file=checkpoint_file)
        translated_structure = translator.translate_structure(structure)

        # STEP 4: Assemble output
        # Progress at 90% through the translation stage
        assembly_progress = int(start_pct + (end_pct - start_pct) * 0.9)
        self.job.update(
            progress=assembly_progress,
            stage_progress={'message': 'Assembling translated markdown...'}
        )
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = self.book_dir / f"{source_path.stem}_{target_lang.replace(' ', '_')}_{timestamp}.md"

        assembler = MarkdownAssembler()
        output_path = assembler.assemble(translated_structure, output_file)

        self.job.output_files['translation'] = str(output_path)
        self.job.update(progress=int(end_pct))

        return output_path

    def _run_summarization(self, input_file: Path) -> Path:
        """
        Run summarization using summarize.py.

        Args:
            input_file: File to summarize

        Returns:
            Path to summarized file
        """
        start_pct, end_pct = self.progress_map.get('summarization', (35, 55))

        self.job.update(
            stage=PipelineStage.SUMMARIZATION,
            progress=int(start_pct),
            stage_progress={'message': 'Starting summarization...'}
        )

        target_pct = self.job.config.get('summarize', 50)

        # Run summarize.py
        cmd = [
            sys.executable,
            str(Path(__file__).parent.parent / "summarize.py"),
            str(input_file),
            str(target_pct)
        ]

        self.job.update(stage_progress={'message': f'Summarizing to {target_pct}%...', 'command': ' '.join(cmd)})

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        # Monitor progress
        for line in iter(process.stdout.readline, ''):
            if self.cancelled:
                process.kill()
                raise Exception("Job cancelled by user")

            # Parse progress
            if 'chunk' in line.lower():
                import re
                match = re.search(r'(\d+)\s*/\s*(\d+)', line)
                if match:
                    current = int(match.group(1))
                    total = int(match.group(2))
                    chunk_progress = int((current / total) * 100)
                    # Use dynamic progress range
                    progress_range = end_pct - start_pct
                    overall_progress = int(start_pct + (chunk_progress * progress_range / 100))
                    self.job.update(
                        progress=overall_progress,
                        stage_progress={
                            'message': f'Summarizing chunk {current}/{total}...',
                            'current_chunk': current,
                            'total_chunks': total
                        }
                    )

        process.wait()

        if process.returncode != 0:
            raise Exception(f"Summarization failed with code {process.returncode}")

        # Find output file
        output_file = input_file.parent / f"{input_file.stem}_summarized_{target_pct}pct.md"
        if not output_file.exists():
            raise Exception("Summarization output file not found")

        self.job.output_files['summarization'] = str(output_file)
        self.job.update(progress=int(end_pct))

        return output_file

    def _run_audio_generation(self, input_file: Path) -> Dict:
        """
        Run audio generation using make_audiobook.py.
        Retries up to AUDIO_MAX_RETRIES times for transient failures.
        Kokoro's chunk-level checkpointing means retries resume from
        where the previous attempt left off (not from scratch).
        """
        start_pct, end_pct = self.progress_map.get('audio_generation', (0, 89))

        self.job.update(
            stage=PipelineStage.AUDIO_GENERATION,
            progress=int(start_pct),
            stage_progress={'message': 'Starting audio generation...'}
        )

        voice = self.job.config.get('voice', 'bf_emma')
        speed = self.job.config.get('speed', 1.0)

        # Pre-flight checks (permanent failures, no retry)
        if not input_file.exists():
            raise Exception(f"Input file not found: {input_file}")

        make_audiobook_script = Path(__file__).parent.parent / "make_audiobook.py"
        if not make_audiobook_script.exists():
            raise Exception(f"make_audiobook.py not found at: {make_audiobook_script}")

        venv_python = Path(__file__).parent.parent / "venv" / "bin" / "python3"
        python_exec = str(venv_python) if venv_python.exists() else sys.executable

        try:
            result = subprocess.run(
                [python_exec, '--version'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                raise Exception(f"Python interpreter check failed: {python_exec}")

            check_cmd = [python_exec, '-c', 'import kokoro_onnx; import soundfile']
            result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                raise Exception(
                    f"Missing dependencies (kokoro-onnx or soundfile)\n"
                    f"Error: {result.stderr}\n\n"
                    f"Fix: Activate venv and run:\n"
                    f"  source venv/bin/activate\n"
                    f"  pip install kokoro-tts kokoro-onnx soundfile"
                )
        except subprocess.TimeoutExpired as e:
            raise Exception(f"Python interpreter check timed out: {e}")
        except Exception as e:
            raise Exception(f"Python interpreter verification failed: {e}")

        # Build command
        cmd = [
            python_exec,
            str(make_audiobook_script),
            str(input_file),
            '--voice', voice,
            '--speed', str(speed),
            '--non-interactive'
        ]

        self.job.update(stage_progress={'message': f'Generating audio with voice {voice}...', 'command': ' '.join(cmd)})

        # Build subprocess environment with explicit venv PATH
        sub_env = os.environ.copy()
        venv_bin = Path(__file__).parent.parent / "venv" / "bin"
        if venv_bin.exists():
            sub_env['PATH'] = str(venv_bin) + ':' + sub_env.get('PATH', '')
            sub_env['VIRTUAL_ENV'] = str(venv_bin.parent)

        # Subprocess execution with retry for transient failures
        last_error_msg = None

        for attempt in range(1, AUDIO_MAX_RETRIES + 1):
            if attempt > 1:
                delay = AUDIO_RETRY_DELAYS[min(attempt - 2, len(AUDIO_RETRY_DELAYS) - 1)]
                self.job.update(stage_progress={
                    'message': f'Retrying audio generation (attempt {attempt}/{AUDIO_MAX_RETRIES}) in {delay}s...',
                    'retry_attempt': attempt,
                    'max_retries': AUDIO_MAX_RETRIES,
                    'voice': voice
                })
                print(f"  [audio] Retry {attempt}/{AUDIO_MAX_RETRIES} in {delay}s "
                      f"(checkpoint will resume from last good chunk)...", flush=True)

                for _ in range(delay):
                    if self.cancelled:
                        raise Exception("Job cancelled by user")
                    time.sleep(1)

            return_code, all_output = self._execute_audio_subprocess(
                cmd, sub_env, voice, start_pct, end_pct
            )

            if return_code == 0:
                break

            # Permanent failure — don't retry
            if self._is_permanent_failure(return_code, all_output):
                print(f"  [audio] Permanent failure (exit code {return_code}), not retrying", flush=True)
                raise Exception(self._build_error_message(return_code, all_output, cmd))

            # Transient failure
            last_error_msg = self._build_error_message(return_code, all_output, cmd)
            print(f"  [audio] Transient failure (exit code {return_code}), "
                  f"attempt {attempt}/{AUDIO_MAX_RETRIES}", flush=True)

            if attempt == AUDIO_MAX_RETRIES:
                raise Exception(
                    f"Audio generation failed after {AUDIO_MAX_RETRIES} attempts.\n\n"
                    f"Last error:\n{last_error_msg}"
                )

        # Find audio output directory
        audio_dir = input_file.parent / "audio_kokoro"
        if not audio_dir.exists():
            raise Exception("Audio output directory not found")

        self.job.output_files['audio'] = str(audio_dir)
        self.job.update(progress=int(end_pct))

        return {
            'output_directory': str(audio_dir),
            'voice': voice,
            'speed': speed
        }

    def _run_cover_generation(self, audio_result: Dict):
        """Generate cover art"""
        start_pct, end_pct = self.progress_map.get('cover_art', (89, 95))

        self.job.update(
            stage=PipelineStage.COVER_ART,
            progress=int(start_pct),
            stage_progress={'message': 'Generating cover art...'}
        )

        # Extract book title
        book_title = self.job.book_id.replace('_', ' ').title()
        audio_dir = Path(audio_result['output_directory'])
        cover_path = audio_dir / f"{self.job.book_id}_cover.png"

        # Check if cover.py exists
        cover_script = Path(__file__).parent.parent / "cover.py"
        if not cover_script.exists():
            self.job.update(progress=int(end_pct), stage_progress={'message': 'Cover generation skipped (cover.py not found)'})
            return

        # Generate cover
        prompt = f"Book cover art for '{book_title}', classic literature style, elegant typography, vintage aesthetic"

        cmd = [
            sys.executable,
            str(cover_script),
            prompt,
            '--output', str(cover_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode == 0:
            self.job.output_files['cover'] = str(cover_path)
        else:
            self.job.update(stage_progress={'message': 'Cover generation failed (non-fatal)'})

        self.job.update(progress=int(end_pct))

    def _run_registration(self, audio_result: Dict):
        """Register audiobook with server"""
        start_pct, end_pct = self.progress_map.get('registration', (95, 100))

        self.job.update(
            stage=PipelineStage.REGISTRATION,
            progress=int(start_pct),
            stage_progress={'message': 'Registering audiobook...'}
        )

        # Create metadata file
        audio_dir = Path(audio_result['output_directory'])
        metadata = {
            'title': self.job.book_id.replace('_', ' ').title(),
            'voice': audio_result['voice'],
            'speed': audio_result['speed'],
            'created_at': datetime.now().isoformat(),
            'source_file': self.job.source_file,
            'pipeline_job_id': self.job.job_id
        }

        if self.job.config.get('translate'):
            metadata['translated_from'] = self.job.config.get('source_language')
            metadata['translated_to'] = self.job.config.get('target_language')

        if self.job.config.get('summarize'):
            metadata['summarized'] = True
            metadata['summary_percentage'] = self.job.config.get('summarize')

        metadata_path = audio_dir / "audiobook_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        self.job.output_files['metadata'] = str(metadata_path)

        self.job.update(progress=100)


if __name__ == '__main__':
    # Test the pipeline directly (without unified queue)
    import argparse

    parser = argparse.ArgumentParser(description="Audiobook Pipeline Test")
    parser.add_argument('book_id', help='Book directory name')
    parser.add_argument('source_file', help='Source markdown file')
    parser.add_argument('--translate', action='store_true', help='Enable translation')
    parser.add_argument('--summarize', type=int, help='Summary percentage (10-90)')
    parser.add_argument('--voice', default='bf_emma', help='Voice ID')
    parser.add_argument('--speed', type=float, default=1.0, help='Playback speed')
    parser.add_argument('--generate-cover', action='store_true', help='Generate cover art')

    args = parser.parse_args()

    config = {
        'translate': args.translate,
        'source_language': 'Russian',
        'target_language': 'Modern English',
        'translation_model': 'zongwei/gemma3-translator:4b',
        'summarize': args.summarize,
        'voice': args.voice,
        'speed': args.speed,
        'generate_cover': args.generate_cover
    }

    job_id = str(uuid.uuid4())
    job = JobState(job_id, args.book_id, args.source_file, config)
    print(f"Created job: {job_id}")

    runner = PipelineRunner(job)
    try:
        runner.run()
        print(f"\nJob completed")
    except Exception as e:
        print(f"\nJob failed: {e}")
