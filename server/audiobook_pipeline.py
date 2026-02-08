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
import threading
import time
import uuid
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List
from enum import Enum

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.language_detector import detect_language


# Constants
BOOKS_DIR = Path(__file__).parent.parent / "books"
JOBS_DIR = Path(__file__).parent / "pipeline_jobs"
MAX_CONCURRENT_JOBS = 2
POLL_INTERVAL = 2.0  # seconds


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


# Global state
jobs_lock = threading.Lock()
jobs = {}  # {job_id: JobState}
job_semaphore = threading.Semaphore(MAX_CONCURRENT_JOBS)


class JobState:
    """Represents a pipeline job with state tracking"""

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

        # Save state
        self.state_file = JOBS_DIR / f"{job_id}.json"
        self._save_state()

    def _save_state(self):
        """Save job state to disk"""
        JOBS_DIR.mkdir(parents=True, exist_ok=True)

        state = {
            'job_id': self.job_id,
            'book_id': self.book_id,
            'source_file': self.source_file,
            'config': self.config,
            'status': self.status,
            'current_stage': self.current_stage,
            'progress': self.progress,
            'stage_progress': self.stage_progress,
            'created_at': self.created_at,
            'updated_at': datetime.now().isoformat(),
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'error': self.error,
            'output_files': self.output_files
        }

        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)

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
        # Calculate ETA
        eta_seconds = None
        if self.status == JobStatus.RUNNING and self.started_at and self.progress > 5:
            elapsed = (datetime.now() - datetime.fromisoformat(self.started_at)).total_seconds()
            estimated_total = elapsed / (self.progress / 100)
            eta_seconds = max(0, estimated_total - elapsed)

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
        self.job.update(
            stage=PipelineStage.LANGUAGE_DETECTION,
            progress=2,
            stage_progress={'message': 'Detecting source language...'}
        )

        source_path = self.book_dir / self.job.source_file
        result = detect_language(source_path)

        self.job.config['detected_language'] = result['language']
        self.job.config['language_confidence'] = result['confidence']
        self.job.update(progress=5)

    def _run_translation(self) -> Path:
        """
        Run translation using OpenAI API or Ollama.

        Returns:
            Path to translated file
        """
        self.job.update(
            stage=PipelineStage.TRANSLATION,
            progress=10,
            stage_progress={'message': 'Starting translation...'}
        )

        source_path = self.book_dir / self.job.source_file
        source_lang = self.job.config.get('source_language', 'Russian')
        target_lang = self.job.config.get('target_language', 'Modern English')
        model = self.job.config.get('translation_model', 'o3-mini-high')

        # Output file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = self.book_dir / f"{source_path.stem}_{target_lang.replace(' ', '_')}_{timestamp}.md"

        # Run translator.py
        cmd = [
            sys.executable,
            str(Path(__file__).parent.parent / "translator.py"),
            str(source_path),
            '--model', model,
            '--source-lang', source_lang,
            '--target-lang', target_lang,
            '--output-dir', str(self.book_dir)
        ]

        self.job.update(stage_progress={'message': f'Translating from {source_lang}...', 'command': ' '.join(cmd)})

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

            # Parse progress from translator output
            # Look for patterns like "Processing chunk 5/20"
            if 'chunk' in line.lower():
                # Extract chunk numbers
                import re
                match = re.search(r'(\d+)\s*/\s*(\d+)', line)
                if match:
                    current = int(match.group(1))
                    total = int(match.group(2))
                    chunk_progress = int((current / total) * 100)
                    overall_progress = 10 + int(chunk_progress * 0.25)  # Translation is 10-35%
                    self.job.update(
                        progress=overall_progress,
                        stage_progress={
                            'message': f'Translating chunk {current}/{total}...',
                            'current_chunk': current,
                            'total_chunks': total
                        }
                    )

        process.wait()

        if process.returncode != 0:
            raise Exception(f"Translation failed with code {process.returncode}")

        # Find output file (translator creates it automatically)
        translated_files = sorted(self.book_dir.glob(f"*{target_lang.replace(' ', '_')}*.md"))
        if not translated_files:
            raise Exception("Translation output file not found")

        output_file = translated_files[-1]  # Get most recent
        self.job.output_files['translation'] = str(output_file)
        self.job.update(progress=35)

        return output_file

    def _run_summarization(self, input_file: Path) -> Path:
        """
        Run summarization using book_summarizer.py.

        Args:
            input_file: File to summarize

        Returns:
            Path to summarized file
        """
        self.job.update(
            stage=PipelineStage.SUMMARIZATION,
            progress=40,
            stage_progress={'message': 'Starting summarization...'}
        )

        target_pct = self.job.config.get('summarize', 50)

        # Run book_summarizer.py
        cmd = [
            sys.executable,
            str(Path(__file__).parent.parent / "book_summarizer.py"),
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
                    overall_progress = 40 + int(chunk_progress * 0.15)  # Summarization is 40-55%
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
        self.job.update(progress=55)

        return output_file

    def _run_audio_generation(self, input_file: Path) -> Dict:
        """
        Run audio generation using make_audiobook.py.

        Args:
            input_file: File to convert to audio

        Returns:
            Audio generation results
        """
        self.job.update(
            stage=PipelineStage.AUDIO_GENERATION,
            progress=60,
            stage_progress={'message': 'Starting audio generation...'}
        )

        voice = self.job.config.get('voice', 'bf_emma')
        speed = self.job.config.get('speed', 1.0)

        # Pre-flight checks
        if not input_file.exists():
            raise Exception(f"Input file not found: {input_file}")

        make_audiobook_script = Path(__file__).parent.parent / "make_audiobook.py"
        if not make_audiobook_script.exists():
            raise Exception(f"make_audiobook.py not found at: {make_audiobook_script}")

        # Use venv Python explicitly (server requires venv for kokoro-onnx)
        # The server is started via start_server.sh which activates venv, so we use that Python
        venv_python = Path(__file__).parent.parent / "venv" / "bin" / "python3"

        # Fallback to sys.executable if venv not found (development mode)
        python_exec = str(venv_python) if venv_python.exists() else sys.executable

        # Verify Python interpreter and dependencies
        try:
            result = subprocess.run(
                [python_exec, '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                raise Exception(f"Python interpreter check failed: {python_exec}")

            # Check kokoro-onnx is installed
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

        # Run make_audiobook.py with non-interactive flag
        cmd = [
            python_exec,
            str(make_audiobook_script),
            str(input_file),
            '--voice', voice,
            '--speed', str(speed),
            '--non-interactive'     # Skip validation prompts
            # Note: Omit --generate-cover (we handle cover separately in _run_cover_generation)
        ]

        self.job.update(stage_progress={'message': f'Generating audio with voice {voice}...', 'command': ' '.join(cmd)})

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        # Capture ALL output for debugging
        all_output = []

        # Monitor progress
        for line in iter(process.stdout.readline, ''):
            if self.cancelled:
                process.kill()
                raise Exception("Job cancelled by user")

            # Store all output for error reporting
            all_output.append(line.rstrip())

            # Parse progress from make_audiobook.py output
            # Look for patterns like "Processing chunk 45/100"
            if 'chunk' in line.lower() or 'processing' in line.lower():
                import re
                match = re.search(r'(\d+)\s*/\s*(\d+)', line)
                if match:
                    current = int(match.group(1))
                    total = int(match.group(2))
                    chunk_progress = int((current / total) * 100)
                    overall_progress = 60 + int(chunk_progress * 0.35)  # Audio is 60-95%
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

        if process.returncode != 0:
            # Build detailed error message with command and output
            error_lines = all_output[-30:] if len(all_output) > 30 else all_output  # Last 30 lines

            # Extract actual error message if available
            actual_error = None
            for line in reversed(all_output):
                if 'ERROR' in line or 'Error' in line or 'error' in line:
                    actual_error = line.strip()
                    break

            error_msg = f"Audio generation failed with exit code {process.returncode}\n\n"

            if actual_error:
                error_msg += f"Error: {actual_error}\n\n"

            error_msg += f"Command: {' '.join(cmd)}\n\n"

            if error_lines:
                error_msg += "Output (last 30 lines):\n"
                error_msg += "\n".join(error_lines)
            else:
                error_msg += "No output captured (process may have crashed immediately)\n"

            error_msg += "\n\n💡 Troubleshooting:\n"
            error_msg += "  - Check that venv is activated: source venv/bin/activate\n"
            error_msg += "  - Verify kokoro-onnx is installed: pip list | grep kokoro\n"
            error_msg += "  - Try running manually: " + ' '.join(cmd)

            raise Exception(error_msg)

        # Find audio output directory
        audio_dir = input_file.parent / "audio_kokoro"
        if not audio_dir.exists():
            raise Exception("Audio output directory not found")

        self.job.output_files['audio'] = str(audio_dir)
        self.job.update(progress=95)

        return {
            'output_directory': str(audio_dir),
            'voice': voice,
            'speed': speed
        }

    def _run_cover_generation(self, audio_result: Dict):
        """Generate cover art"""
        self.job.update(
            stage=PipelineStage.COVER_ART,
            progress=96,
            stage_progress={'message': 'Generating cover art...'}
        )

        # Extract book title
        book_title = self.job.book_id.replace('_', ' ').title()
        audio_dir = Path(audio_result['output_directory'])
        cover_path = audio_dir / f"{self.job.book_id}_cover.png"

        # Check if generate.py exists
        generate_script = Path(__file__).parent.parent / "generate.py"
        if not generate_script.exists():
            self.job.update(progress=98, stage_progress={'message': 'Cover generation skipped (generate.py not found)'})
            return

        # Generate cover
        prompt = f"Book cover art for '{book_title}', classic literature style, elegant typography, vintage aesthetic"

        cmd = [
            sys.executable,
            str(generate_script),
            prompt,
            '--output', str(cover_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode == 0:
            self.job.output_files['cover'] = str(cover_path)
        else:
            self.job.update(stage_progress={'message': 'Cover generation failed (non-fatal)'})

        self.job.update(progress=98)

    def _run_registration(self, audio_result: Dict):
        """Register audiobook with server"""
        self.job.update(
            stage=PipelineStage.REGISTRATION,
            progress=99,
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


# ============================================================================
# Public API
# ============================================================================

def create_job(
    book_id: str,
    source_file: str,
    config: Dict
) -> str:
    """
    Create a new pipeline job.

    Args:
        book_id: Book directory name
        source_file: Source markdown filename
        config: Job configuration

    Returns:
        job_id
    """
    job_id = str(uuid.uuid4())

    # Create job
    job = JobState(job_id, book_id, source_file, config)

    with jobs_lock:
        jobs[job_id] = job

    # Start worker thread
    thread = threading.Thread(target=_run_job, args=(job_id,), daemon=True)
    thread.start()

    return job_id


def get_job(job_id: str) -> Optional[Dict]:
    """Get job status"""
    with jobs_lock:
        job = jobs.get(job_id)
        if job:
            return job.to_dict()
    return None


def get_all_jobs() -> List[Dict]:
    """Get all jobs"""
    with jobs_lock:
        return [job.to_dict() for job in jobs.values()]


def cancel_job(job_id: str) -> bool:
    """Cancel a running job"""
    with jobs_lock:
        job = jobs.get(job_id)
        if job and job.status in [JobStatus.PENDING, JobStatus.RUNNING]:
            job.update(status=JobStatus.CANCELLED)
            return True
    return False


def _run_job(job_id: str):
    """Worker thread to run a job"""
    with job_semaphore:  # Limit concurrent jobs
        with jobs_lock:
            job = jobs.get(job_id)

        if not job:
            return

        try:
            runner = PipelineRunner(job)
            runner.run()
        except Exception as e:
            print(f"❌ Job {job_id} failed: {e}")
            job.update(status=JobStatus.FAILED, error=str(e))


# Load existing jobs on startup
def load_existing_jobs():
    """Load job state from disk"""
    if not JOBS_DIR.exists():
        return

    for state_file in JOBS_DIR.glob("*.json"):
        try:
            with open(state_file, 'r') as f:
                state_data = json.load(f)

            # Recreate job object
            job = JobState(
                state_data['job_id'],
                state_data['book_id'],
                state_data['source_file'],
                state_data['config']
            )

            # Restore state
            job.status = state_data['status']
            job.current_stage = state_data['current_stage']
            job.progress = state_data['progress']
            job.stage_progress = state_data['stage_progress']
            job.created_at = state_data['created_at']
            job.updated_at = state_data['updated_at']
            job.started_at = state_data.get('started_at')
            job.completed_at = state_data.get('completed_at')
            job.error = state_data.get('error')
            job.output_files = state_data.get('output_files', {})

            with jobs_lock:
                jobs[job.job_id] = job

        except Exception as e:
            print(f"⚠️  Failed to load job {state_file}: {e}")


# Load existing jobs on module import
load_existing_jobs()


if __name__ == '__main__':
    # Test the pipeline
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
        'translation_model': 'o3-mini-high',
        'summarize': args.summarize,
        'voice': args.voice,
        'speed': args.speed,
        'generate_cover': args.generate_cover
    }

    job_id = create_job(args.book_id, args.source_file, config)
    print(f"✅ Created job: {job_id}")

    # Monitor progress
    while True:
        job = get_job(job_id)
        if not job:
            break

        print(f"\r[{job['progress']:3d}%] {job['current_stage']:20s} - {job.get('stage_progress', {}).get('message', '')}", end='', flush=True)

        if job['status'] in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            print()
            break

        time.sleep(2)

    print(f"\n{'✅' if job['status'] == JobStatus.COMPLETED else '❌'} Job {job['status']}")
    if job.get('error'):
        print(f"Error: {job['error']}")
