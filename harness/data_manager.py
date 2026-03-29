from pathlib import Path

from harness import schemas


def audit_data_sizes(tests_root='tests', max_test_mb=10.0, max_total_mb=500.0):
    tests_root = Path(tests_root)
    per_test = []
    total_bytes = 0

    for domain_dir in sorted(d for d in tests_root.iterdir() if d.is_dir()):
        manifest = domain_dir / 'manifest.json'
        if not manifest.exists():
            continue
        meta = schemas.load_json(manifest)
        for item in meta.get('tests', []):
            test_id = item.get('test_id')
            if not test_id:
                continue
            task_path = domain_dir / test_id / 'task.json'
            if not task_path.exists():
                continue
            task = schemas.load_json(task_path)
            data_files = task.get('context', {}).get('data_files', [])
            size = 0
            missing = []
            for rel in data_files:
                p = task_path.parent / 'data' / rel
                if p.exists():
                    size += p.stat().st_size
                else:
                    missing.append(str(p))
            total_bytes += size
            per_test.append(
                {
                    'domain': domain_dir.name,
                    'test_id': test_id,
                    'data_bytes': size,
                    'data_mb': round(size / (1024 * 1024), 6),
                    'missing_data_files': missing,
                }
            )

    max_test_bytes = int(max_test_mb * 1024 * 1024)
    max_total_bytes = int(max_total_mb * 1024 * 1024)
    per_test_violations = [p for p in per_test if p['data_bytes'] > max_test_bytes]
    missing_files = [p for p in per_test if p['missing_data_files']]

    return {
        'tests_total': len(per_test),
        'max_test_mb': max_test_mb,
        'max_total_mb': max_total_mb,
        'total_data_bytes': total_bytes,
        'total_data_mb': round(total_bytes / (1024 * 1024), 6),
        'total_size_violation': total_bytes > max_total_bytes,
        'per_test_size_violations': per_test_violations,
        'tests_with_missing_data_files': missing_files,
        'per_test': per_test,
    }
