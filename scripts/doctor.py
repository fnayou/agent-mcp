import os, shutil, subprocess, sys
missing = [name for name in ('git', 'python3', 'uv') if not shutil.which(name)]
for name in missing:
    print(f'MISSING: {name}')
if missing:
    print('Install missing tools and rerun task doctor.')
    sys.exit(1)
print('OK: local prerequisites found', flush=True)
manifest = subprocess.run(['uv', 'run', '--quiet', '--locked', '--script', 'scripts/manifest_check.py'])
if manifest.returncode:
    sys.exit(manifest.returncode)
docker = shutil.which('docker')
if not docker:
    print('NOT CHECKED: Compose config; Docker CLI is missing.')
    sys.exit(1)
version = subprocess.run([docker, 'compose', 'version'], capture_output=True, text=True)
if version.returncode:
    print('NOT CHECKED: Compose config; Docker Compose plugin is missing.')
    sys.exit(1)
result = subprocess.run([docker, 'compose', '-f', 'compose.example.yaml', 'config', '--quiet'], capture_output=True, text=True)
if result.returncode:
    print('INVALID: Compose config; run task setup and review YAML and interpolation values.')
    sys.exit(result.returncode)
print('OK: Compose config')
key_dir = os.environ.get('SOPS_AGE_KEY_DIR') or os.path.expanduser('~/.config/sops/age')
if not os.path.isfile(os.path.join(key_dir, 'keys.txt')):
    print('MISSING: age key; copy keys.txt from another machine or run task secrets:keygen.')
    sys.exit(1)
print('OK: age key', flush=True)
decrypt = subprocess.run([docker, 'compose', '-f', 'compose.example.yaml', 'run', '--rm', '-T', '--user', f'{os.getuid()}:{os.getgid()}', 'sops', 'decrypt', 'secrets.sops.yaml'], capture_output=True)
if decrypt.returncode:
    print('INVALID: secrets.sops.yaml does not decrypt with the local age key')
    sys.exit(1)
print('OK: secrets.sops.yaml decrypts', flush=True)
harnesses = subprocess.run(['uv', 'run', '--quiet', '--locked', '--script', 'scripts/installer.py', 'status'])
sys.exit(harnesses.returncode)
