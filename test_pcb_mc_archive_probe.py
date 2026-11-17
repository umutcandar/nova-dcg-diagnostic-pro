"""Unit tests for read-only 4TU PCB-MC ZIP metadata probe, no internet."""
import io
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile, ZIP_DEFLATED

from pcb_mc_archive_probe import (
    ProbeError, select_official_file, read_remote_zip_names, parse_directory,
    EXPECTED_FILENAME, EXPECTED_SIZE, EXPECTED_MD5,
)


class PCBMCArchiveProbeTests(unittest.TestCase):
    def make_zip(self):
        out=io.BytesIO()
        with ZipFile(out,"w",ZIP_DEFLATED) as z:
            z.writestr("PCB_MC/images/pcb_001.jpg",b"fake image")
            z.writestr("PCB_MC/annotations/PCB-MC-C/fold_0/train.json",b"{}")
            z.writestr("PCB_MC/annotations/PCB-MC-C/fold_0/valid.json",b"{}")
            z.writestr("PCB_MC/splits/components_only_splits.json",b"{}")
        return out.getvalue()

    def test_parse_real_zip_central_directory_with_range_mock(self):
        zipped=self.make_zip()
        def fake_range(url,start,end,size):
            self.assertEqual(size,len(zipped))
            return zipped[start:end+1]
        with patch("pcb_mc_archive_probe.download_range",side_effect=fake_range):
            report=read_remote_zip_names("https://example.org/PCB_MC.zip",len(zipped))
        self.assertEqual(report["state"],"verified_zip_directory")
        self.assertEqual(len(report["entries"]),4)
        self.assertIn("PCB_MC/splits/components_only_splits.json",report["entries"])

    def test_zip64_locator_can_describe_the_same_small_synthetic_archive(self):
        zipped=self.make_zip()
        eocd=zipped.rfind(b"PK\x05\x06")
        self.assertGreater(eocd,0)
        sig,disk,disk_cd,one,total,cd_size,cd_offset,comment=struct.unpack_from(
            "<4s4H2IH",zipped,eocd
        )
        zip64_offset=eocd
        zip64_record=struct.pack(
            "<4sQ2H2I4Q",b"PK\x06\x06",44,45,45,0,0,
            total,total,cd_size,cd_offset
        )
        locator=struct.pack("<4sIQI",b"PK\x06\x07",0,zip64_offset,1)
        stub=struct.pack("<4s4H2IH",b"PK\x05\x06",0,0,
                         65535,65535,0xffffffff,0xffffffff,0)
        payload=zipped[:eocd]+zip64_record+locator+stub
        def fake_range(url,start,end,size):
            self.assertEqual(size,len(payload))
            return payload[start:end+1]
        with patch("pcb_mc_archive_probe.download_range",side_effect=fake_range):
            result=read_remote_zip_names("https://example.org/PCB_MC.zip",len(payload))
        self.assertEqual(result["state"],"verified_zip_directory")
        self.assertEqual(len(result["entries"]),4)

    def test_unsupported_range_does_not_download_all(self):
        with patch("pcb_mc_archive_probe.download_range",return_value=None):
            report=read_remote_zip_names("https://example.org/data",3772070324)
        self.assertEqual(report["state"],"range_unsupported")
        self.assertEqual(report["entries"],[])

    def test_bad_zip_directory_rejected(self):
        with self.assertRaisesRegex(ProbeError,"header"):
            parse_directory(b"\0"*46,1)

    def test_official_metadata_requires_verified_archive_size_md5(self):
        files=[{
            "name":EXPECTED_FILENAME,"size":EXPECTED_SIZE,
            "computed_md5":EXPECTED_MD5,
            "download_url":"https://download.example.org/PCB_MC.zip",
        }]
        self.assertEqual(select_official_file([{"id":123}],files)["size"],EXPECTED_SIZE)
        files[0]["computed_md5"]="0"*32
        with self.assertRaisesRegex(ProbeError,"MD5"):
            select_official_file([{"id":123}],files)

    def test_non_tls_url_is_rejected(self):
        files=[{
            "name":EXPECTED_FILENAME,"size":EXPECTED_SIZE,
            "computed_md5":EXPECTED_MD5,
            "download_url":"http://insecure.example.org/model.zip",
        }]
        with self.assertRaisesRegex(ProbeError,"HTTPS"):
            select_official_file([{"id":123}],files)


if __name__=="__main__":
    unittest.main()
