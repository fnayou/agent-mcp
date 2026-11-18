import os, shutil, stat, subprocess, sys, urllib.error, urllib.request
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
key_file = 'age/key.txt'
if not os.path.isfile(key_file):
    print('MISSING: age key; copy age/key.txt from another machine or, on the very first machine only, run task sops:generate-age-key.')
    sys.exit(1)
if stat.S_IMODE(os.stat(key_file).st_mode) != 0o600:
    print('INVALID: age/key.txt is not mode 600; run chmod 600 age/key.txt')
    sys.exit(1)
print('OK: age key (age/key.txt, mode 600)', flush=True)
validate = subprocess.run(['sh', 'secrets/validate-secrets.sh'])
if validate.returncode:
    sys.exit(validate.returncode)
decrypt = subprocess.run([docker, 'compose', '-f', 'compose.example.yaml', 'run', '--rm', '-T', '--user', f'{os.getuid()}:{os.getgid()}', 'sops', '--config', 'secrets/.sops.yaml', 'decrypt', 'secrets/secrets.sops.yaml'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
if decrypt.returncode:
    print('INVALID: secrets/secrets.sops.yaml does not decrypt with age/key.txt')
    sys.exit(1)
print('OK: secrets/secrets.sops.yaml decrypts', flush=True)
harnesses = subprocess.run(['uv', 'run', '--quiet', '--locked', '--script', 'scripts/installer.py', 'status'])
# Not running is a warning, not a failure: the operator may not have logged in yet.
running = subprocess.run([docker, 'compose', '-f', 'compose.example.yaml', 'ps', '--status', 'running', '--quiet', 'telegram'], capture_output=True, text=True)
if running.returncode or not running.stdout.strip():
    print('WARNING: telegram container is not running; run task telegram:login once, then task telegram:up.')
else:
    print('OK: telegram container is running')
telegram_url = 'http://127.0.0.1:8765/mcp'
try:
    urllib.request.urlopen(telegram_url, timeout=5).close()
    answered = True
except urllib.error.HTTPError:
    answered = True  # any HTTP response counts
except (urllib.error.URLError, OSError):
    answered = False
print(f'OK: {telegram_url} answers' if answered else f'WARNING: {telegram_url} does not answer')
sys.exit(harnesses.returncode)
