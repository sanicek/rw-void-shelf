"""Exercise release contracts without requiring RimWorld, .NET, or a network."""

from __future__ import annotations

import importlib.util
import hashlib
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from project import Project, ProjectError, load_project  # noqa: E402
from release_archive import ArchiveError, copy_verified_archive, extract_release  # noqa: E402


def script_module(name: str, filename: str):
    """Load command scripts whose hyphenated filenames are not import names."""

    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


packager = script_module("package_release", "package-release.py")
source_validator = script_module("validate_source", "validate-source.py")


def metadata_text(version: str = "1.0.0") -> str:
    """Describe the intended Void Shelf release identity for isolated fixtures."""

    return f"""<?xml version="1.0" encoding="utf-8"?>
<ModMetaData>
  <name>Void Shelf</name>
  <author>Sanicek</author>
  <packageId>Sanicek.VoidShelf</packageId>
  <modVersion>{version}</modVersion>
  <supportedVersions><li>1.5</li><li>1.6</li></supportedVersions>
  <description>Fixture package.</description>
</ModMetaData>
"""


class PackageFixture:
    """Create a small runtime package for archive tests, with no real assembly."""

    def __init__(self, root: Path) -> None:
        self.package = root / "VoidShelf"
        (self.package / "About").mkdir(parents=True)
        (self.package / "1.5" / "Defs").mkdir(parents=True)
        (self.package / "1.6" / "Defs").mkdir(parents=True)
        (self.package / "About" / "About.xml").write_text(metadata_text(), encoding="utf-8")
        (self.package / "LoadFolders.xml").write_text(
            "<loadFolders><v1.5><li>1.5</li></v1.5><v1.6><li>1.6</li></v1.6></loadFolders>\n",
            encoding="utf-8",
        )
        (self.package / "1.5" / "Defs" / "Buildings.xml").write_text("<Defs />\n", encoding="utf-8")
        (self.package / "1.6" / "Defs" / "Buildings.xml").write_text("<Defs />\n", encoding="utf-8")


class RealPackageFixture:
    """Assemble a validator fixture from tracked payloads without compiling."""

    def __init__(self, root: Path) -> None:
        self.package = root / "VoidShelf"
        shutil.copytree(REPO_ROOT / "About", self.package / "About")
        shutil.copytree(REPO_ROOT / "1.5", self.package / "1.5")
        shutil.copytree(REPO_ROOT / "1.6", self.package / "1.6")
        shutil.copytree(REPO_ROOT / "Languages", self.package / "Languages")
        shutil.copyfile(REPO_ROOT / "LoadFolders.xml", self.package / "LoadFolders.xml")
        shutil.copyfile(REPO_ROOT / "LICENSE", self.package / "LICENSE")
        assemblies = self.package / "1.6" / "Assemblies"
        assemblies.mkdir()
        (assemblies / "VoidShelf.dll").write_bytes(b"active fixture")

    def validate(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, SCRIPTS / "validate-package.py", self.package],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )


class ProjectTests(unittest.TestCase):
    """Keep metadata parsing strict enough to safely derive release names."""

    def test_void_shelf_identity_and_semver_are_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            metadata = Path(temporary) / "About.xml"
            metadata.write_text(metadata_text(), encoding="utf-8")
            project = load_project(metadata)
            self.assertEqual(project.package_name, "VoidShelf")
            self.assertEqual(project.version, "1.0.0")
            self.assertEqual(project.supported_versions, ("1.5", "1.6"))

    def test_prerelease_and_leading_zero_versions_are_rejected(self) -> None:
        for version in ("1.0.0-rc.1", "01.0.0"):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as temporary:
                metadata = Path(temporary) / "About.xml"
                metadata.write_text(metadata_text(version), encoding="utf-8")
                with self.assertRaisesRegex(ProjectError, "MAJOR.MINOR.PATCH"):
                    load_project(metadata)

    def test_repository_metadata_has_the_release_identity(self) -> None:
        project = load_project(REPO_ROOT / "About" / "About.xml")
        self.assertEqual((project.package_id, project.version), ("Sanicek.VoidShelf", "1.1.0"))
        self.assertIn(
            f"docs/releases/{project.version}.md",
            (REPO_ROOT / "README.md").read_text(encoding="utf-8"),
        )


class PackageValidatorTests(unittest.TestCase):
    """Exercise release layout and the recovered payload boundary directly."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.fixture = RealPackageFixture(Path(self.temporary.name))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_valid_fixture_passes(self) -> None:
        result = self.fixture.validate()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_changed_or_expanded_frozen_runtime_is_rejected(self) -> None:
        buildings = self.fixture.package / "1.5" / "Defs" / "Buildings.xml"
        assembly = self.fixture.package / "1.5" / "Assemblies" / "VoidShelf.dll"
        original = buildings.read_bytes()
        original_assembly = assembly.read_bytes()
        for mutation in ("changed-def", "changed-dll", "extra", "empty-directory"):
            with self.subTest(mutation=mutation):
                buildings.write_bytes(original)
                assembly.write_bytes(original_assembly)
                extra = buildings.with_name("Injected.xml")
                extra.unlink(missing_ok=True)
                if mutation == "changed-def":
                    buildings.write_bytes(original + b"\n")
                elif mutation == "changed-dll":
                    assembly.write_bytes(original_assembly + b"\x00")
                elif mutation == "extra":
                    extra.write_text("<Defs />\n", encoding="utf-8")
                else:
                    (buildings.parent / "Empty").mkdir()
                result = self.fixture.validate()
                self.assertNotEqual(result.returncode, 0)
                shutil.rmtree(buildings.parent / "Empty", ignore_errors=True)
        buildings.write_bytes(original)
        assembly.write_bytes(original_assembly)

    def test_identity_and_filesystem_violations_are_rejected(self) -> None:
        cases = ("workshop", "url", "symlink", "fifo")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                fixture = RealPackageFixture(Path(temporary))
                if case == "workshop":
                    (fixture.package / "About" / "PublishedFileId.txt").write_text("1\n", encoding="ascii")
                elif case == "url":
                    metadata = fixture.package / "About" / "About.xml"
                    metadata.write_text(metadata.read_text(encoding="utf-8").replace("rw-void-shelf", "wrong"), encoding="utf-8")
                elif case == "symlink":
                    (fixture.package / "1.6" / "Defs" / "Link.xml").symlink_to("Buildings.xml")
                else:
                    os.mkfifo(fixture.package / "1.6" / "Defs" / "pipe")
                self.assertNotEqual(fixture.validate().returncode, 0)

    def test_translation_coverage_and_shared_routing_are_required(self) -> None:
        for case in ("missing-catalog", "wrong-key", "english-fallback", "missing-root-route"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                fixture = RealPackageFixture(Path(temporary))
                catalog = fixture.package / "Languages" / "French" / "DefInjected" / "ThingDef" / "Buildings.xml"
                if case == "missing-catalog":
                    catalog.unlink()
                elif case == "wrong-key":
                    catalog.write_text(
                        catalog.read_text(encoding="utf-8").replace("VoidShelf.description", "VoidShelf.wrong"),
                        encoding="utf-8",
                    )
                elif case == "english-fallback":
                    catalog.write_text(
                        catalog.read_text(encoding="utf-8").replace("étagère du néant", "Void Shelf"),
                        encoding="utf-8",
                    )
                else:
                    load_folders = fixture.package / "LoadFolders.xml"
                    load_folders.write_text(
                        load_folders.read_text(encoding="utf-8").replace("    <li>/</li>\n", ""),
                        encoding="utf-8",
                    )
                self.assertNotEqual(fixture.validate().returncode, 0)

    def test_ambiguous_or_expanded_translation_catalogs_are_rejected(self) -> None:
        cases = ("duplicate", "blank", "nested", "extra-catalog", "extra-language")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                fixture = RealPackageFixture(Path(temporary))
                french = fixture.package / "Languages" / "French"
                catalog = french / "DefInjected" / "ThingDef" / "Buildings.xml"
                text = catalog.read_text(encoding="utf-8")
                if case == "duplicate":
                    catalog.write_text(
                        text.replace("</LanguageData>", "  <VoidShelf.label>duplicata</VoidShelf.label>\n</LanguageData>"),
                        encoding="utf-8",
                    )
                elif case == "blank":
                    catalog.write_text(
                        text.replace("étagère du néant", "   ", 1),
                        encoding="utf-8",
                    )
                elif case == "nested":
                    catalog.write_text(
                        text.replace("étagère du néant", "<b>étagère du néant</b>", 1),
                        encoding="utf-8",
                    )
                elif case == "extra-catalog":
                    (catalog.parent / "Other.xml").write_text("<LanguageData />\n", encoding="utf-8")
                else:
                    shutil.copytree(french, fixture.package / "Languages" / "Italian")
                self.assertNotEqual(fixture.validate().returncode, 0)

    def test_root_runtime_content_and_cross_version_routes_are_rejected(self) -> None:
        for case in ("root-defs", "root-assemblies", "wrong-version", "both-versions"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                fixture = RealPackageFixture(Path(temporary))
                if case == "root-defs":
                    (fixture.package / "Defs").mkdir()
                elif case == "root-assemblies":
                    (fixture.package / "Assemblies").mkdir()
                else:
                    load_folders = fixture.package / "LoadFolders.xml"
                    text = load_folders.read_text(encoding="utf-8")
                    if case == "wrong-version":
                        text = text.replace("    <li>1.5</li>", "    <li>1.6</li>", 1)
                    else:
                        text = text.replace("    <li>1.5</li>", "    <li>1.5</li>\n    <li>1.6</li>", 1)
                    load_folders.write_text(text, encoding="utf-8")
                self.assertNotEqual(fixture.validate().returncode, 0)


class ReleaseArchiveTests(unittest.TestCase):
    """Prove deterministic publication and same-version immutability."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.fixture = PackageFixture(self.root)
        self.project = Project("Void Shelf", "Sanicek", "Sanicek.VoidShelf", "VoidShelf", "1.0.0", ("1.5", "1.6"))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_archive_bytes_and_sha256_sidecar_are_deterministic(self) -> None:
        first = self.root / "first.zip"
        second = self.root / "second.zip"
        packager.write_archive(self.fixture.package, first)
        packager.write_archive(self.fixture.package, second)
        self.assertEqual(first.read_bytes(), second.read_bytes())

        archive, digest = packager.publish_archive(self.fixture.package, self.root / "releases", self.project)
        repeated, repeated_digest = packager.publish_archive(self.fixture.package, self.root / "releases", self.project)
        self.assertEqual(archive, repeated)
        self.assertEqual(digest, repeated_digest)
        self.assertEqual(archive.with_suffix(".zip.sha256").read_text(encoding="ascii"), f"{digest}  {archive.name}\n")

    def test_differing_same_version_archive_is_not_replaced(self) -> None:
        archive, _ = packager.publish_archive(self.fixture.package, self.root / "releases", self.project)
        original = archive.read_bytes()
        (self.fixture.package / "1.6" / "Defs" / "Buildings.xml").write_text("<Defs><Changed /></Defs>\n", encoding="utf-8")
        with self.assertRaisesRegex(packager.ReleaseError, "same-version candidate differs"):
            packager.publish_archive(self.fixture.package, self.root / "releases", self.project)
        self.assertEqual(archive.read_bytes(), original)

    def test_accepted_digest_is_enforced_without_existing_artifacts(self) -> None:
        with self.assertRaisesRegex(packager.ReleaseError, "accepted checksum"):
            packager.publish_archive(
                self.fixture.package,
                self.root / "releases",
                self.project,
                expected_digest="0" * 64,
            )
        self.assertFalse((self.root / "releases" / "VoidShelf-v1.0.0.zip").exists())

    def test_orphaned_or_nonregular_sidecar_blocks_publication(self) -> None:
        for sidecar_kind in ("stale", "directory"):
            with self.subTest(sidecar_kind=sidecar_kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fixture = PackageFixture(root)
                release_dir = root / "releases"
                release_dir.mkdir()
                sidecar = release_dir / "VoidShelf-v1.0.0.zip.sha256"
                if sidecar_kind == "stale":
                    sidecar.write_text(f"{'0' * 64}  VoidShelf-v1.0.0.zip\n", encoding="ascii")
                else:
                    sidecar.mkdir()
                with self.assertRaises(packager.ReleaseError):
                    packager.publish_archive(fixture.package, release_dir, self.project)
                self.assertFalse((release_dir / "VoidShelf-v1.0.0.zip").exists())

    def test_package_symlink_is_rejected(self) -> None:
        source = self.fixture.package / "1.6" / "Defs" / "Buildings.xml"
        (source.parent / "Link.xml").symlink_to(source)
        with self.assertRaisesRegex(packager.ReleaseError, "symlinks"):
            packager.write_archive(self.fixture.package, self.root / "release.zip")


class ExtractionTests(unittest.TestCase):
    """Reject hostile ZIP forms before any package becomes visible."""

    def archive(self, root: Path, entries: list[tuple[zipfile.ZipInfo | str, bytes]]) -> Path:
        path = root / "release.zip"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("VoidShelf/", b"")
            for name, content in entries:
                archive.writestr(name, content)
        return path

    def test_valid_archive_extracts_under_single_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self.archive(root, [("VoidShelf/About/About.xml", metadata_text().encode())])
            destination = root / "destination"
            destination.mkdir()
            package = extract_release(archive, destination, "VoidShelf")
            self.assertTrue((package / "About" / "About.xml").is_file())

    def test_traversal_and_windows_separators_are_rejected(self) -> None:
        for name in ("VoidShelf/../outside", "VoidShelf\\outside"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                archive = self.archive(root, [(name, b"bad")])
                destination = root / "destination"
                destination.mkdir()
                with self.assertRaises(ArchiveError):
                    extract_release(archive, destination, "VoidShelf")
                self.assertEqual(list(destination.iterdir()), [])

    def test_symlink_and_special_file_modes_are_rejected(self) -> None:
        for file_type in (stat.S_IFLNK, stat.S_IFIFO):
            with self.subTest(file_type=file_type), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                entry = zipfile.ZipInfo("VoidShelf/link")
                entry.create_system = 3
                entry.external_attr = (file_type | 0o777) << 16
                archive = self.archive(root, [(entry, b"target")])
                destination = root / "destination"
                destination.mkdir()
                with self.assertRaisesRegex(ArchiveError, "link or special"):
                    extract_release(archive, destination, "VoidShelf")

    def test_high_compression_ratio_is_rejected_without_partial_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self.archive(root, [("VoidShelf/large.txt", b"0" * 1024 * 1024)])
            destination = root / "destination"
            destination.mkdir()
            with self.assertRaisesRegex(ArchiveError, "compression ratio"):
                extract_release(archive, destination, "VoidShelf")
            self.assertEqual(list(destination.iterdir()), [])

    def test_existing_target_and_symlinked_destination_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self.archive(root, [("VoidShelf/file", b"data")])
            destination = root / "destination"
            (destination / "VoidShelf").mkdir(parents=True)
            with self.assertRaisesRegex(ArchiveError, "already exists"):
                extract_release(archive, destination, "VoidShelf")
            link = root / "linked"
            link.symlink_to(destination, target_is_directory=True)
            with self.assertRaisesRegex(ArchiveError, "real directory"):
                extract_release(archive, link, "VoidShelf")

    def test_unsafe_package_name_argument_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self.archive(root, [("VoidShelf/file", b"data")])
            destination = root / "destination"
            destination.mkdir()
            with self.assertRaisesRegex(ArchiveError, "package name"):
                extract_release(archive, destination, "../outside")

    def test_checksum_must_name_and_match_the_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self.archive(root, [("VoidShelf/file", b"expected")])
            canonical_archive = root / "VoidShelf-v1.0.0.zip"
            archive.rename(canonical_archive)
            archive = canonical_archive
            destination = root / "destination"
            destination.mkdir()
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            checksum = root / "release.zip.sha256"
            for text in (
                f"{digest}  alternate.zip\n",
                f"{'0' * 64}  {archive.name}\n",
                f"{digest}  {archive.name}\nextra",
            ):
                with self.subTest(text=text):
                    checksum.write_text(text, encoding="ascii")
                    with self.assertRaises(ArchiveError):
                        copy_verified_archive(archive, checksum, destination)
                    self.assertEqual(list(destination.iterdir()), [])

            checksum.write_text(f"{digest}  {archive.name}\n", encoding="ascii")
            verified = copy_verified_archive(archive, checksum, destination)
            archive.write_bytes(b"replaced after verification")
            package = extract_release(verified, destination, "VoidShelf")
            self.assertEqual((package / "file").read_bytes(), b"expected")

    def test_duplicate_sibling_and_truncated_archives_leave_no_package(self) -> None:
        for case in ("duplicate", "sibling", "truncated"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                archive_path = root / "release.zip"
                with zipfile.ZipFile(archive_path, "w") as archive:
                    archive.writestr("VoidShelf/", b"")
                    archive.writestr("VoidShelf/file", b"one")
                    if case == "duplicate":
                        archive.writestr("VoidShelf/file", b"two")
                    elif case == "sibling":
                        archive.writestr("OtherMod/file", b"two")
                if case == "truncated":
                    archive_path.write_bytes(archive_path.read_bytes()[:-10])
                destination = root / "destination"
                destination.mkdir()
                with self.assertRaises(ArchiveError):
                    extract_release(archive_path, destination, "VoidShelf")
                self.assertEqual(list(destination.iterdir()), [])


class WorkflowGateTests(unittest.TestCase):
    """Exercise Git gates without invoking the assembly build."""

    def test_clean_worktree_gate_rejects_untracked_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
            tracked = repo / "tracked"
            tracked.write_text("clean\n", encoding="ascii")
            subprocess.run(["git", "add", "tracked"], cwd=repo, check=True)
            subprocess.run(
                ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture"],
                cwd=repo,
                check=True,
            )
            packager.require_clean_worktree(repo)
            (repo / "untracked").write_text("dirty\n", encoding="ascii")
            with self.assertRaisesRegex(packager.ReleaseError, "clean worktree"):
                packager.require_clean_worktree(repo)

    def test_tagged_release_checksum_cannot_be_rewritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            record = repo / "docs" / "releases" / "1.0.0.md"
            record.parent.mkdir(parents=True)
            digest_a = "a" * 64
            digest_b = "b" * 64
            record.write_text(f"| Candidate SHA-256 | `{digest_a}` |\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(
                ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "release"],
                cwd=repo,
                check=True,
            )
            subprocess.run(["git", "tag", "v1.0.0"], cwd=repo, check=True)
            project = Project("Void Shelf", "Sanicek", "Sanicek.VoidShelf", "VoidShelf", "1.0.0", ("1.5", "1.6"))
            self.assertEqual(packager.accepted_checksum(repo, project), digest_a)
            record.write_text(f"| Candidate SHA-256 | `{digest_b}` |\n", encoding="utf-8")
            with self.assertRaisesRegex(packager.ReleaseError, "does not match"):
                packager.accepted_checksum(repo, project)


class SourceContractTests(unittest.TestCase):
    """Pin the repository-specific identity and recovered 1.5 integrity values."""

    def test_frozen_15_hashes_match_repository_bytes(self) -> None:
        for relative, expected in source_validator.FROZEN_PAYLOAD_HASHES["1.5"].items():
            path = REPO_ROOT / "1.5" / relative
            self.assertEqual(source_validator.hashlib.sha256(path.read_bytes()).hexdigest(), expected)

    def test_tracked_release_record_validates_without_building(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "repo"
            shutil.copytree(
                REPO_ROOT,
                repo,
                ignore=shutil.ignore_patterns(".git", "artifacts", "__pycache__", "*.pyc", "bin", "obj"),
            )
            subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            source_validator.validate_source(repo, release=True)

            (repo / "docs" / "releases" / "1.1.0.md").unlink()
            with self.assertRaisesRegex(source_validator.SourceError, "release record is required"):
                source_validator.validate_source(repo, release=True)

    def test_extra_frozen_runtime_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "repo"
            shutil.copytree(
                REPO_ROOT,
                repo,
                ignore=shutil.ignore_patterns(".git", "artifacts", "__pycache__", "*.pyc", "bin", "obj"),
            )
            subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            for mutation in ("file", "empty-directory"):
                with self.subTest(mutation=mutation):
                    injected = repo / "1.5" / "Defs" / ("Injected.xml" if mutation == "file" else "Empty")
                    if mutation == "file":
                        injected.write_text("<Defs />\n", encoding="utf-8")
                    else:
                        injected.mkdir()
                    with self.assertRaisesRegex(source_validator.SourceError, "unexpected entries"):
                        source_validator.validate_source(repo)
                    if injected.is_dir():
                        injected.rmdir()
                    else:
                        injected.unlink()

    def test_bogus_inherited_lock_descriptor_is_rejected(self) -> None:
        result = subprocess.run(
            [SCRIPTS / "build.sh"],
            cwd=REPO_ROOT,
            env={**os.environ, "ARTIFACT_LOCK_FD": "9999"},
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("inherited open descriptor", result.stderr)


if __name__ == "__main__":
    unittest.main()
