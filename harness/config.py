import os


def default_run_config():
    return {
        'suite': os.getenv('BIOTASKBENCH_SUITE', 'biotaskbench'),
        'tests_root': os.getenv('BIOTASKBENCH_TESTS_ROOT', 'tests'),
        'output_dir': os.getenv('BIOTASKBENCH_OUTPUT_DIR', 'results'),
        'workspace_root': os.getenv('BIOTASKBENCH_WORKSPACE_ROOT'),
        'model': os.getenv('BIOTASKBENCH_MODEL'),
        'skills_path': os.getenv('BIOTASKBENCH_SKILLS_PATH'),
        'timeout_minutes': int(os.getenv('BIOTASKBENCH_TIMEOUT_MINUTES', '10')),
    }
