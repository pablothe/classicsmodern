#!/usr/bin/env python3
"""
Pipeline Handler - Full audiobook pipeline worker

Wraps PipelineRunner for unified job queue.
Executes: Translation → Summarization → Audio → Cover → Registration
"""

from pathlib import Path
from typing import Dict, Callable

from server.audiobook_pipeline import PipelineRunner


class ProgressAdapter:
    """
    Adapts PipelineRunner's internal updates to unified queue format.
    """

    def __init__(self, job_data: Dict, progress_callback: Callable):
        """
        Initialize adapter.

        Args:
            job_data: Original job data
            progress_callback: Unified queue progress callback
        """
        self.job_data = job_data
        self.progress_callback = progress_callback
        self.pipeline_job = None

    def attach(self, pipeline_job):
        """
        Attach to PipelineRunner job state.

        Args:
            pipeline_job: JobState instance from audiobook_pipeline
        """
        self.pipeline_job = pipeline_job

        # Override the job's update method to intercept calls
        original_update = pipeline_job.update

        def wrapped_update(**kwargs):
            # Call original update
            original_update(**kwargs)

            # Extract progress and stage info
            progress = kwargs.get('progress', pipeline_job.progress)
            stage_progress = kwargs.get('stage_progress', pipeline_job.stage_progress)

            # Build state dict for unified queue
            state = {
                'stage': pipeline_job.current_stage,
                'message': stage_progress.get('message', '') if stage_progress else '',
                'details': stage_progress
            }

            # Report to unified queue
            self.progress_callback(progress, state)

        # Replace update method
        pipeline_job.update = wrapped_update


def pipeline_handler(job: Dict, progress_callback: Callable) -> Dict:
    """
    Handle full audiobook pipeline job.

    Args:
        job: Job data dictionary with:
            - config.book_id: Book directory name
            - config.source_file: Source markdown filename
            - config.translate: Enable translation
            - config.source_language: Source language
            - config.target_language: Target language
            - config.translation_model: Translation model
            - config.summarize: Optional summary percentage (10-90)
            - config.voice: Voice ID (e.g., 'bf_emma')
            - config.speed: Playback speed
            - config.generate_cover: Whether to generate cover art
        progress_callback: Function to report progress
            Signature: progress_callback(progress: int, state: Dict)

    Returns:
        Result dictionary with:
            - output_files: Dictionary of output files per stage
            - metadata: Audiobook metadata

    Raises:
        Exception on pipeline failure
    """
    config = job['config']
    book_id = config['book_id']
    source_file = config['source_file']

    # Import JobState to create pipeline job
    from server.audiobook_pipeline import JobState

    # Create a temporary job ID for the pipeline (internal tracking)
    import uuid
    internal_job_id = str(uuid.uuid4())

    # Create pipeline job state
    pipeline_job = JobState(
        job_id=internal_job_id,
        book_id=book_id,
        source_file=source_file,
        config=config
    )

    # Attach progress adapter
    adapter = ProgressAdapter(job, progress_callback)
    adapter.attach(pipeline_job)

    # Create pipeline runner
    runner = PipelineRunner(pipeline_job)

    try:
        # Run the pipeline (this will automatically report progress via adapter)
        runner.run()

        # Return results
        return {
            'output_files': pipeline_job.output_files,
            'book_id': book_id,
            'source_file': source_file,
            'config': config
        }

    except Exception as e:
        # Re-raise with context
        raise Exception(f"Pipeline failed: {str(e)}")
