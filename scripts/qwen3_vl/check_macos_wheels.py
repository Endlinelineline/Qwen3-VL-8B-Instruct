"""Check mandatory macOS dependencies in downloaded wheel metadata and build a hash lock."""
from email.parser import BytesParser
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[2]
wheelhouse = ROOT / 'macos_offline/wheelhouse'
packages = {}
for wheel in sorted(wheelhouse.glob('*.whl')):
    with ZipFile(wheel) as archive:
        metadata = BytesParser().parsebytes(archive.read(next(n for n in archive.namelist() if n.endswith('.dist-info/METADATA'))))
    name = canonicalize_name(metadata['Name'])
    if name in packages:
        raise ValueError(f'Duplicate wheel: {name}')
    packages[name] = (wheel, metadata)
if not packages:
    raise ValueError('No wheels found')
environment = {'sys_platform': 'darwin', 'platform_system': 'Darwin', 'platform_machine': 'arm64',
               'os_name': 'posix', 'python_version': '3.11', 'python_full_version': '3.11.9',
               'implementation_name': 'cpython', 'platform_python_implementation': 'CPython', 'extra': ''}
for name, (_, metadata) in packages.items():
    for dependency in metadata.get_all('Requires-Dist', []):
        requirement = Requirement(dependency)
        if requirement.marker and not requirement.marker.evaluate(environment):
            continue
        target = canonicalize_name(requirement.name)
        if target not in packages or Version(packages[target][1]['Version']) not in requirement.specifier:
            raise ValueError(f'{name}: missing or incompatible dependency {requirement}')
lines = ['# Apple Silicon, CPython 3.11. Offline wheel hashes.']
for name, (wheel, metadata) in sorted(packages.items()):
    digest = sha256(wheel.read_bytes()).hexdigest()
    lines.append(f'{name}=={metadata["Version"]} --hash=sha256:{digest}')
(ROOT / 'macos_offline/requirements-locked.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(f'Validated {len(packages)} wheel metadata records; wrote hash lock.')
