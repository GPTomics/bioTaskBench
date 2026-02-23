import json
from pathlib import Path

CRITERION_TYPES = {
    'file_check', 'column_check', 'exact_match', 'range_check', 'set_overlap', 'numeric_correlation', 'code_executes', 'llm_judge'
}

SET_OVERLAP_METRICS = {'peak_count_jaccard', 'element_jaccard', 'f1'}
CORR_METRICS = {'pearson', 'spearman'}
MATCH_TYPES = {'exact', 'case_insensitive', 'substring_case_insensitive'}
LLM_SCORING = {'binary', 'scale'}

COMMON_REQUIRED = {'name', 'type', 'description', 'weight'}

REQUIRED_BY_TYPE = {
    'file_check': {'target_pattern'},
    'column_check': {'target_file', 'required_columns'},
    'exact_match': {'target_file', 'target'},
    'range_check': {'target_file', 'field', 'range'},
    'set_overlap': {'expected_file', 'target_file', 'metric'},
    'numeric_correlation': {'expected_file', 'target_file', 'field', 'metric'},
    'code_executes': {'target_pattern'},
    'llm_judge': {'target_file', 'rubric'},
}


def load_json(path):
    path = Path(path)
    with path.open() as f:
        return json.load(f)


def validate_task(task, task_path=None):
    errors = []
    required = {'test_id', 'version', 'domain', 'difficulty', 'prompt', 'context', 'evaluation', 'metadata'}
    missing_top = required - set(task)
    if missing_top:
        errors.append(f'missing top-level fields: {sorted(missing_top)}')
        return errors

    if task['evaluation'].get('type') != 'multi_criteria':
        errors.append('evaluation.type must be multi_criteria')

    criteria = task['evaluation'].get('criteria', [])
    if not isinstance(criteria, list) or not criteria:
        errors.append('evaluation.criteria must be a non-empty list')
        return errors

    total_weight = 0.0
    for i, criterion in enumerate(criteria):
        prefix = f'criteria[{i}]'
        missing = COMMON_REQUIRED - set(criterion)
        if missing:
            errors.append(f'{prefix} missing required fields: {sorted(missing)}')
            continue

        ctype = criterion.get('type')
        if ctype not in CRITERION_TYPES:
            errors.append(f'{prefix} has unknown type: {ctype}')
            continue

        total_weight += float(criterion.get('weight', 0.0))

        required_fields = REQUIRED_BY_TYPE[ctype]
        missing_specific = required_fields - set(criterion)
        if missing_specific:
            errors.append(f'{prefix} ({ctype}) missing fields: {sorted(missing_specific)}')

        if ctype == 'set_overlap':
            metric = criterion.get('metric')
            if metric not in SET_OVERLAP_METRICS:
                errors.append(f'{prefix} invalid set_overlap metric: {metric}')

        if ctype == 'numeric_correlation':
            metric = criterion.get('metric')
            if metric not in CORR_METRICS:
                errors.append(f'{prefix} invalid numeric_correlation metric: {metric}')

        if ctype == 'exact_match':
            match_type = criterion.get('match_type', 'exact')
            if match_type not in MATCH_TYPES:
                errors.append(f'{prefix} invalid match_type: {match_type}')

        if ctype == 'llm_judge':
            scoring = criterion.get('scoring', 'binary')
            if scoring not in LLM_SCORING:
                errors.append(f'{prefix} invalid llm_judge scoring: {scoring}')

        if ctype == 'range_check':
            r = criterion.get('range')
            if not _is_valid_range(r):
                errors.append(f'{prefix} range must be [min, max] with min <= max')
            pr = criterion.get('partial_range')
            if pr is not None and not _is_valid_range(pr):
                errors.append(f'{prefix} partial_range must be [min, max] with min <= max')
            if pr is not None and 'partial_score' not in criterion:
                errors.append(f'{prefix} partial_range requires partial_score')

    if abs(total_weight - 1.0) > 1e-6:
        errors.append(f'criteria weights must sum to 1.0 (got {total_weight:.6f})')

    if task_path:
        errors.extend(validate_task_files(task, task_path))

    return errors


def validate_task_files(task, task_path):
    errors = []
    task_path = Path(task_path)
    test_dir = task_path.parent

    for i, criterion in enumerate(task.get('evaluation', {}).get('criteria', [])):
        prefix = f'criteria[{i}]'
        expected_file = criterion.get('expected_file')
        if expected_file:
            p = test_dir / expected_file
            if not p.exists():
                errors.append(f'{prefix} expected_file missing: {expected_file}')

    return errors


def validate_manifest(manifest, manifest_path=None):
    errors = []
    required = {'domain', 'display_name', 'description', 'tests'}
    missing = required - set(manifest)
    if missing:
        errors.append(f'manifest missing fields: {sorted(missing)}')
        return errors

    tests = manifest.get('tests', [])
    if not isinstance(tests, list) or not tests:
        errors.append('manifest tests must be a non-empty list')
        return errors

    for i, t in enumerate(tests):
        if 'test_id' not in t:
            errors.append(f'manifest tests[{i}] missing test_id')

    if manifest_path:
        errors.extend(validate_manifest_files(manifest, manifest_path))

    return errors


def validate_manifest_files(manifest, manifest_path):
    errors = []
    manifest_path = Path(manifest_path)
    domain_dir = manifest_path.parent

    declared = {item['test_id'] for item in manifest.get('tests', []) if 'test_id' in item}
    for test_id in sorted(declared):
        task_path = domain_dir / test_id / 'task.json'
        if not task_path.exists():
            errors.append(f'manifest test_id not found on disk: {test_id}')

    return errors


def _is_valid_range(vals):
    if not isinstance(vals, list) or len(vals) != 2:
        return False
    try:
        lo = float(vals[0])
        hi = float(vals[1])
    except Exception:
        return False
    return lo <= hi
