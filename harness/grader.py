import csv
import glob
import math
import os
import re
import subprocess
from pathlib import Path


def grade_task(task, workspace_dir, test_dir):
    workspace_dir = Path(workspace_dir)
    test_dir = Path(test_dir)

    attempted = detect_attempted(task, workspace_dir)
    criteria_results = []
    criteria_scores = {}
    weighted = 0.0

    for criterion in task['evaluation']['criteria']:
        result = grade_criterion(criterion, workspace_dir, test_dir)
        criteria_results.append(result)
        criteria_scores[criterion['name']] = result['score']
        weighted += float(criterion['weight']) * float(result['score'])

    return {
        'test_id': task['test_id'],
        'suite': 'biotaskbench',
        'attempted': attempted,
        'score': float(weighted),
        'criteria_scores': criteria_scores,
        'criteria_results': criteria_results,
    }


def detect_attempted(task, workspace_dir):
    workspace_dir = Path(workspace_dir)
    for criterion in task['evaluation']['criteria']:
        if criterion.get('target_file') and (workspace_dir / criterion['target_file']).exists():
            return True
        if criterion.get('target_pattern'):
            matches = glob.glob(str(workspace_dir / criterion['target_pattern']))
            if matches:
                return True
    return False


def grade_criterion(criterion, workspace_dir, test_dir):
    ctype = criterion['type']
    try:
        if ctype == 'file_check':
            return _grade_file_check(criterion, workspace_dir)
        if ctype == 'column_check':
            return _grade_column_check(criterion, workspace_dir)
        if ctype == 'exact_match':
            return _grade_exact_match(criterion, workspace_dir)
        if ctype == 'range_check':
            return _grade_range_check(criterion, workspace_dir)
        if ctype == 'set_overlap':
            return _grade_set_overlap(criterion, workspace_dir, test_dir)
        if ctype == 'numeric_correlation':
            return _grade_numeric_correlation(criterion, workspace_dir, test_dir)
        if ctype == 'code_executes':
            return _grade_code_executes(criterion, workspace_dir)
        if ctype == 'llm_judge':
            return {'score': 0.0, 'details': 'llm_judge not implemented in phase 1'}
        return {'score': 0.0, 'details': f'unknown criterion type: {ctype}'}
    except Exception as e:
        return {'score': 0.0, 'details': f'criterion evaluation error: {e}'}


def _grade_file_check(criterion, workspace_dir):
    pattern = str(Path(workspace_dir) / criterion['target_pattern'])
    matches = [Path(p) for p in glob.glob(pattern)]
    if not matches:
        return {'score': 0.0, 'details': 'no matching file'}

    min_columns = criterion.get('min_columns')
    if min_columns:
        file_path = matches[0]
        first = _first_data_line(file_path)
        if first is None:
            return {'score': 0.0, 'details': 'file empty'}
        columns = len(first.rstrip('\n').split('\t'))
        if columns < int(min_columns):
            return {'score': 0.0, 'details': f'expected >= {min_columns} columns, found {columns}'}

    return {'score': 1.0, 'details': f'matched {len(matches)} file(s)'}


def _grade_column_check(criterion, workspace_dir):
    path = Path(workspace_dir) / criterion['target_file']
    if not path.exists():
        return {'score': 0.0, 'details': 'target_file missing'}

    header = _read_header(path)
    required = criterion['required_columns']
    missing = [c for c in required if c not in header]
    if missing:
        return {'score': 0.0, 'details': f'missing columns: {missing}'}
    return {'score': 1.0, 'details': 'all required columns present'}


def _grade_exact_match(criterion, workspace_dir):
    path = Path(workspace_dir) / criterion['target_file']
    if not path.exists():
        return {'score': 0.0, 'details': 'target_file missing'}

    target = str(criterion['target'])
    match_type = criterion.get('match_type', 'exact')
    exclude_patterns = [p.lower() for p in criterion.get('exclude_patterns', [])]
    field = criterion.get('field')

    rows = _read_rows(path)
    haystack = []

    if field:
        for row in rows:
            value = str(row.get(field, ''))
            if not value:
                continue
            haystack.append(value)
    else:
        with path.open() as f:
            haystack = [line.rstrip('\n') for line in f if line.strip()]

    filtered = []
    for value in haystack:
        lv = value.lower()
        if any(p in lv for p in exclude_patterns):
            continue
        filtered.append(value)

    matched = any(_matches(v, target, match_type) for v in filtered)
    return {'score': 1.0 if matched else 0.0, 'details': 'match found' if matched else 'no match'}


def _grade_range_check(criterion, workspace_dir):
    path = Path(workspace_dir) / criterion['target_file']
    if not path.exists():
        return {'score': 0.0, 'details': 'target_file missing'}

    value = _extract_range_value(path, criterion['field'])
    if value is None:
        return {'score': 0.0, 'details': 'could not extract numeric value'}

    if _in_range(value, criterion['range']):
        return {'score': 1.0, 'details': f'value={value} in full range'}

    if criterion.get('partial_range') is not None and _in_range(value, criterion['partial_range']):
        return {'score': float(criterion.get('partial_score', 0.0)), 'details': f'value={value} in partial range'}

    return {'score': 0.0, 'details': f'value={value} outside ranges'}


def _grade_set_overlap(criterion, workspace_dir, test_dir):
    target_path = Path(workspace_dir) / criterion['target_file']
    expected_path = Path(test_dir) / criterion['expected_file']
    if not target_path.exists():
        return {'score': 0.0, 'details': 'target_file missing'}
    if not expected_path.exists():
        return {'score': 0.0, 'details': 'expected_file missing'}

    metric = criterion['metric']
    min_acceptable = criterion.get('min_acceptable')

    if metric == 'peak_count_jaccard':
        slop = int(criterion.get('slop_bp', 0))
        truth = _read_intervals(expected_path)
        pred = _read_intervals(target_path)
        score = _peak_count_jaccard(truth, pred, slop)
    elif metric == 'element_jaccard':
        field = criterion.get('field')
        truth = _read_elements(expected_path, field)
        pred = _read_elements(target_path, field, criterion.get('filter_field'), criterion.get('filter_value'))
        score = _jaccard(truth, pred)
    elif metric == 'f1':
        field = criterion.get('field')
        truth = _read_elements(expected_path, field)
        pred = _read_elements(target_path, field, criterion.get('filter_field'), criterion.get('filter_value'))
        score = _f1(truth, pred)
    else:
        return {'score': 0.0, 'details': f'unsupported metric: {metric}'}

    raw = score
    if min_acceptable is not None and score < float(min_acceptable):
        score = 0.0

    return {'score': float(score), 'details': f'raw={raw:.4f} min_acceptable={min_acceptable}'}


def _grade_numeric_correlation(criterion, workspace_dir, test_dir):
    target_path = Path(workspace_dir) / criterion['target_file']
    expected_path = Path(test_dir) / criterion['expected_file']
    if not target_path.exists():
        return {'score': 0.0, 'details': 'target_file missing'}
    if not expected_path.exists():
        return {'score': 0.0, 'details': 'expected_file missing'}

    field = criterion['field']
    join_field = criterion.get('join_field')
    metric = criterion['metric']

    x, y = _paired_numeric_vectors(expected_path, target_path, field, join_field)
    if len(x) < 2 or len(y) < 2:
        return {'score': 0.0, 'details': 'insufficient paired numeric values'}

    if metric == 'pearson':
        score = _pearson(x, y)
    else:
        score = _spearman(x, y)

    if math.isnan(score):
        score = 0.0

    raw = score
    min_acceptable = criterion.get('min_acceptable')
    if min_acceptable is not None and score < float(min_acceptable):
        score = 0.0

    return {'score': float(score), 'details': f'raw={raw:.4f} min_acceptable={min_acceptable}'}


def _grade_code_executes(criterion, workspace_dir):
    pattern = str(Path(workspace_dir) / criterion['target_pattern'])
    matches = [Path(p) for p in glob.glob(pattern)]
    if not matches:
        return {'score': 0.0, 'details': 'no code files matched'}

    language = criterion.get('language', 'python')
    timeout = int(criterion.get('timeout_seconds', 60))
    file_path = matches[0]

    if language == 'python':
        cmd = ['python3', str(file_path)]
    elif language == 'r':
        cmd = ['Rscript', str(file_path)]
    else:
        return {'score': 0.0, 'details': f'unsupported language: {language}'}

    completed = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if completed.returncode == 0:
        return {'score': 1.0, 'details': 'code executed successfully'}
    return {'score': 0.0, 'details': f'non-zero exit code: {completed.returncode}'}


def _extract_range_value(path, field):
    if field.startswith('custom:'):
        name = field.split(':', 1)[1]
        fn = CUSTOM_HANDLERS.get(name)
        if not fn:
            return None
        return fn(path)

    if field == 'row_count':
        return _row_count(path)

    if field.startswith('top_'):
        column = field[4:]
        rows = _read_rows(path)
        if not rows:
            return None
        return _to_float(rows[0].get(column))

    if field.startswith('count_where:'):
        expr = field.split(':', 1)[1]
        column, value = expr.split('=', 1)
        rows = _read_rows(path)
        return sum(1 for row in rows if str(row.get(column, '')) == value)

    if field.startswith('pct_where:'):
        expr = field.split(':', 1)[1]
        column, value = expr.split('=', 1)
        rows = _read_rows(path)
        if not rows:
            return 0.0
        count = sum(1 for row in rows if str(row.get(column, '')) == value)
        return (count / len(rows)) * 100.0

    rows = _read_rows(path)
    if not rows:
        return None
    return _to_float(rows[0].get(field))


def _row_count(path):
    with path.open() as f:
        lines = [line for line in f if line.strip()]

    if not lines:
        return 0

    has_header = _has_header(path)
    return max(0, len(lines) - (1 if has_header else 0))


def _has_header(path):
    with path.open() as f:
        sample = f.read(4096)
    if not sample.strip():
        return False
    try:
        return csv.Sniffer().has_header(sample)
    except Exception:
        return False


def _read_header(path):
    with path.open() as f:
        line = f.readline().rstrip('\n')
    delimiter = _detect_delimiter(path)
    return [c.strip() for c in line.split(delimiter)]


def _read_rows(path):
    delimiter = _detect_delimiter(path)
    with path.open() as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            has_header = csv.Sniffer().has_header(sample)
        except Exception:
            has_header = True

        if has_header:
            reader = csv.DictReader(f, delimiter=delimiter)
            return [dict(row) for row in reader]

        rows = []
        for idx, line in enumerate(f):
            if not line.strip():
                continue
            parts = line.rstrip('\n').split(delimiter)
            rows.append({f'col_{i+1}': val for i, val in enumerate(parts)})
        return rows


def _read_rows_force_header(path):
    delimiter = _detect_delimiter(path)
    with path.open() as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        return [dict(row) for row in reader]


def _detect_delimiter(path):
    with path.open() as f:
        first = f.readline()
    if '\t' in first:
        return '\t'
    if ',' in first:
        return ','
    return '\t'


def _first_data_line(path):
    with path.open() as f:
        for line in f:
            if line.strip():
                return line
    return None


def _matches(value, target, match_type):
    value = str(value)
    target = str(target)
    if match_type == 'exact':
        return value == target
    if match_type == 'case_insensitive':
        return value.lower() == target.lower()
    if match_type == 'substring_case_insensitive':
        return target.lower() in value.lower()
    return False


def _in_range(value, bounds):
    lo = float(bounds[0])
    hi = float(bounds[1])
    v = float(value)
    return lo <= v <= hi


def _read_intervals(path):
    intervals = []
    with path.open() as f:
        for line in f:
            if not line.strip() or line.startswith('#'):
                continue
            parts = line.rstrip('\n').split('\t')
            if len(parts) < 3:
                continue
            chrom = parts[0]
            start = _to_int(parts[1])
            end = _to_int(parts[2])
            if start is None or end is None:
                continue
            intervals.append((chrom, start, end))
    return intervals


def _peak_count_jaccard(truth, pred, slop):
    if not truth and not pred:
        return 1.0
    if not truth or not pred:
        return 0.0

    used_truth = set()
    used_pred = set()

    pred_by_chr = {}
    for j, p in enumerate(pred):
        pred_by_chr.setdefault(p[0], []).append((j, p))

    matches = 0
    for i, t in enumerate(truth):
        chrom = t[0]
        candidates = pred_by_chr.get(chrom, [])
        t_start, t_end = t[1] - slop, t[2] + slop
        for j, p in candidates:
            if j in used_pred:
                continue
            p_start, p_end = p[1] - slop, p[2] + slop
            if t_end < p_start or p_end < t_start:
                continue
            if i in used_truth:
                continue
            used_truth.add(i)
            used_pred.add(j)
            matches += 1
            break

    denom = len(truth) + len(pred) - matches
    if denom <= 0:
        return 0.0
    return matches / denom


def _read_elements(path, field=None, filter_field=None, filter_value=None):
    rows = _read_rows(path)
    if not rows:
        return set()

    if field is None:
        key = next(iter(rows[0]))
    else:
        if field not in rows[0]:
            forced = _read_rows_force_header(path)
            if forced:
                rows = forced
        key = field

    result = set()
    for row in rows:
        if filter_field is not None and str(row.get(filter_field, '')) != str(filter_value):
            continue
        value = row.get(key)
        if value is None or str(value).strip() == '':
            continue
        result.add(str(value))
    return result


def _jaccard(a, b):
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _f1(truth, pred):
    if not truth and not pred:
        return 1.0
    tp = len(truth & pred)
    fp = len(pred - truth)
    fn = len(truth - pred)
    if tp == 0:
        return 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _paired_numeric_vectors(expected_path, target_path, field, join_field=None):
    expected_rows = _read_rows(expected_path)
    target_rows = _read_rows(target_path)
    if expected_rows and (field not in expected_rows[0] or (join_field and join_field not in expected_rows[0])):
        forced = _read_rows_force_header(expected_path)
        if forced:
            expected_rows = forced
    if target_rows and (field not in target_rows[0] or (join_field and join_field not in target_rows[0])):
        forced = _read_rows_force_header(target_path)
        if forced:
            target_rows = forced

    if join_field:
        exp = {str(r.get(join_field)): r for r in expected_rows if r.get(join_field) is not None}
        tgt = {str(r.get(join_field)): r for r in target_rows if r.get(join_field) is not None}
        keys = [k for k in exp if k in tgt]
        x = [_to_float(exp[k].get(field)) for k in keys]
        y = [_to_float(tgt[k].get(field)) for k in keys]
    else:
        n = min(len(expected_rows), len(target_rows))
        x = [_to_float(expected_rows[i].get(field)) for i in range(n)]
        y = [_to_float(target_rows[i].get(field)) for i in range(n)]

    pairs = [(a, b) for a, b in zip(x, y) if a is not None and b is not None and not math.isnan(a) and not math.isnan(b)]
    if not pairs:
        return [], []
    return [p[0] for p in pairs], [p[1] for p in pairs]


def _pearson(x, y):
    n = len(x)
    if n < 2:
        return 0.0
    mx = sum(x) / n
    my = sum(y) / n
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    den_x = math.sqrt(sum((a - mx) ** 2 for a in x))
    den_y = math.sqrt(sum((b - my) ** 2 for b in y))
    if den_x == 0 or den_y == 0:
        return 0.0
    return num / (den_x * den_y)


def _spearman(x, y):
    rx = _ranks(x)
    ry = _ranks(y)
    return _pearson(rx, ry)


def _ranks(values):
    indexed = sorted((v, i) for i, v in enumerate(values))
    ranks = [0.0] * len(values)

    i = 0
    while i < len(indexed):
        j = i
        while j < len(indexed) and indexed[j][0] == indexed[i][0]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            _, idx = indexed[k]
            ranks[idx] = avg_rank
        i = j

    return ranks


def _to_float(value):
    if value is None:
        return None
    s = str(value).strip()
    if s == '':
        return None
    try:
        return float(s)
    except Exception:
        s2 = re.sub(r'[^0-9eE+\-.]', '', s)
        try:
            return float(s2)
        except Exception:
            return None


def _to_int(value):
    try:
        return int(float(str(value)))
    except Exception:
        return None


def custom_unique_non_ctcf_count(path):
    rows = _read_rows(path)
    if not rows:
        return 0

    key = 'motif_name' if 'motif_name' in rows[0] else next(iter(rows[0]))
    names = set()
    for row in rows:
        val = str(row.get(key, '')).strip()
        if not val:
            continue
        lv = val.lower()
        if 'ctcf' in lv or 'ctcfl' in lv or 'boris' in lv:
            continue
        names.add(val)
    return len(names)


def custom_max_missing_pct(path):
    rows = _read_rows(path)
    if not rows:
        return 0.0
    if 'missing_pct' not in rows[0]:
        forced = _read_rows_force_header(path)
        if forced:
            rows = forced
    vals = []
    for row in rows:
        v = _to_float(row.get('missing_pct'))
        if v is not None and not math.isnan(v):
            vals.append(v)
    if not vals:
        return 0.0
    return max(vals)


def custom_max_unstable_pct(path):
    rows = _read_rows(path)
    if not rows:
        return 0.0
    if 'unstable_pct' not in rows[0]:
        forced = _read_rows_force_header(path)
        if forced:
            rows = forced
    vals = []
    for row in rows:
        v = _to_float(row.get('unstable_pct'))
        if v is not None and not math.isnan(v):
            vals.append(v)
    if not vals:
        return 0.0
    return max(vals)


CUSTOM_HANDLERS = {
    'unique_non_ctcf_count': custom_unique_non_ctcf_count,
    'max_missing_pct': custom_max_missing_pct,
    'max_unstable_pct': custom_max_unstable_pct,
}
