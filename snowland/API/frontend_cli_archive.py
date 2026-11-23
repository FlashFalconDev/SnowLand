"""Extra ZIP restrictions for builds uploaded by the CLI."""
import stat
import struct
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZIP_DEFLATED, ZIP_STORED, ZipFile, is_zipfile
from zlib import error as ZipDataError

from . import frontend_publish as publish

STATIC_EXTENSIONS = frozenset({'.html', '.js', '.css', '.png', '.jpg', '.jpeg', '.webp', '.svg'})
ZIP_END = b'PK\x05\x06'
ZIP_END_WINDOW = 22 + 65535  # End of central directory plus the longest legal comment.
MAX_DIRECTORY_BYTES = 8 * 1024 * 1024
FORBIDDEN_SIGNATURES = (
    b'PK\x03\x04', ZIP_END, b'PK\x07\x08', b'MZ', b'\x7fELF', b'#!',
    b'\xfe\xed\xfa\xce', b'\xfe\xed\xfa\xcf', b'\xce\xfa\xed\xfe', b'\xcf\xfa\xed\xfe',
    b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca', b'\xca\xfe\xba\xbf', b'\xbf\xba\xfe\xca',
)


def check_directory(upload):
    # ZipFile allocates the central directory and entry objects at open time.
    # The CLI's limits fit standard ZIP, so bound those allocations before opening it.
    upload.seek(0)
    if upload.read(4) != b'PK\x03\x04':
        raise BadZipFile
    start = max(0, upload.size - ZIP_END_WINDOW)
    upload.seek(start)
    tail = upload.read()
    end = tail.rfind(ZIP_END)
    if end < 0:
        raise BadZipFile
    disk, directory_disk, disk_count, count, size, offset, comment = struct.unpack_from('<4H2IH', tail, end + 4)
    if (disk or directory_disk or disk_count != count or not 0 < count <= publish.MAX_FILES
            or size > MAX_DIRECTORY_BYTES or offset + size != start + end or end + 22 + comment != len(tail)):
        raise BadZipFile
    upload.seek(0)
    return count


def validate_entries(entries, prefix):
    # Track implicit directories as well, e.g. Assets/a.js and assets/b.js collide.
    paths = {}
    explicit_paths = set()
    protected_roots = {path.rstrip('/') for path in publish.PROTECTED}
    for entry in entries:
        path = entry.orig_filename.removesuffix('/') if entry.is_dir() else entry.orig_filename
        mode = stat.S_IFMT(entry.external_attr >> 16)
        expected_mode = stat.S_IFDIR if entry.is_dir() else stat.S_IFREG
        if (not publish.valid_path(path, prefix) or path.casefold() in protected_roots
                or entry.filename != entry.orig_filename or mode not in (0, expected_mode)
                or entry.flag_bits & 1 or entry.compress_type not in (ZIP_STORED, ZIP_DEFLATED)
                or path in explicit_paths or (entry.is_dir() and entry.file_size)):
            raise publish.PublishError('ZIP 含有不支援的路徑、重複項目、連結或加密檔案。')
        if not entry.is_dir() and path != '_redirects' and PurePosixPath(path).suffix.lower() not in STATIC_EXTENSIONS:
            raise publish.PublishError('ZIP 只接受 SnowLand 靜態資產。')
        explicit_paths.add(path)
        parts = PurePosixPath(path)
        for parent in (*reversed(parts.parents[:-1]), parts):
            name = parent.as_posix()
            identity = (name, parent != parts or entry.is_dir())
            if paths.setdefault(name.casefold(), identity) != identity:
                raise publish.PublishError('ZIP 含有大小寫或檔案與目錄路徑衝突。')


def validate_contents(archive, entries):
    for entry in entries:
        # Read to EOF for CRC. Keep only the tail needed to detect a nested ZIP
        # with an allowlisted suffix, including ZIPs with a prepended header.
        with archive.open(entry) as source:
            chunk = source.read(1024 * 1024)
            if chunk.startswith(FORBIDDEN_SIGNATURES):
                raise publish.PublishError('ZIP 含有巢狀壓縮檔或可執行檔。')
            tail = chunk[-ZIP_END_WINDOW:]
            while chunk := source.read(1024 * 1024):
                tail = (tail + chunk)[-ZIP_END_WINDOW:]
            if ZIP_END in tail and is_zipfile(BytesIO(tail)):
                raise publish.PublishError('ZIP 含有巢狀壓縮檔。')


def validate_archive(upload, prefix):
    try:
        count = check_directory(upload)
        with ZipFile(upload) as archive:
            entries = archive.infolist()
            if len(entries) != count:
                raise BadZipFile
            validate_entries(entries, prefix)
            publish.validate_build(archive, prefix=prefix, verify_crc=False)
            validate_contents(archive, entries)
    except (BadZipFile, EOFError, RuntimeError, OSError, ValueError, AttributeError, struct.error, ZipDataError) as exc:
        raise publish.PublishError('ZIP 檔案已損毀或格式不支援。') from exc
    finally:
        upload.seek(0)
