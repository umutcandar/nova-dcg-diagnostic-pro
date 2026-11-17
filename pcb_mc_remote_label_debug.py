"""Read one PUBLIC PCB-MC YOLO label from the official ZIP with HTTP Range.

No full archive download. ZIP64 catalog is used to locate one named file,
then the central CRC32, uncompressed size and compression method are checked.
Never execute bytes or accept archive paths as filesystem destinations.
"""
import argparse
import json
import struct
import zlib
from pathlib import Path

from pcb_mc_archive_probe import (
    API, DIRECT_UUID, DOI, EXPECTED_SIZE, ProbeError, get_json,
    select_official_file, read_remote_zip_names, download_range
)

MAX_TARGET_BYTES=512*1024


def read_remote_member(url,archive_size,entry):
    if entry["compressed_size"]>MAX_TARGET_BYTES or entry["uncompressed_size"]>MAX_TARGET_BYTES:
        raise ProbeError("Target public label file exceeds safe metadata inspection size")
    offset=entry["local_offset"]
    if offset==0xffffffff:
        raise ProbeError("ZIP64 local file offsets not yet supported for targeted entry")
    local=download_range(url,offset,offset+29,archive_size)
    if local is None or len(local)!=30 or local[:4]!=b"PK\x03\x04":
        raise ProbeError("Expected local ZIP file header not found")
    flags,compression=struct.unpack_from("<HH",local,6)
    fname_len,extra_len=struct.unpack_from("<HH",local,26)
    if flags&1:
        raise ProbeError("Encrypted ZIP member cannot be inspected")
    if compression!=entry["method"]:
        raise ProbeError("Central/local compression method mismatch")
    begin=offset+30+fname_len+extra_len
    end=begin+entry["compressed_size"]-1
    if end>=archive_size:
        raise ProbeError("Compressed ZIP entry exceeds source archive")
    compressed=download_range(url,begin,end,archive_size)
    if compressed is None:
        raise ProbeError("Host did not support requested targeted range")
    if compression==0:
        raw=compressed
    elif compression==8:
        raw=zlib.decompress(compressed,-15)
    else:
        raise ProbeError("Unsupported compression method for text label")
    if len(raw)!=entry["uncompressed_size"] or zlib.crc32(raw)&0xffffffff!=entry["crc32"]:
        raise ProbeError("Target ZIP member checksum failed")
    return raw


def inspect_label(filename):
    if not filename or "/" in filename or "\\" in filename or filename.startswith(".") or not filename.endswith(".txt"):
        raise ProbeError("Provide only a public YOLO TXT basename")
    article=get_json(API+"/articles/"+DIRECT_UUID)
    if not str(article.get("doi","")).startswith(DOI):
        raise ProbeError("Wrong official 4TU DOI")
    item=select_official_file([article],get_json(API+"/articles/"+DIRECT_UUID+"/files"))
    catalog=read_remote_zip_names(item["download_url"],EXPECTED_SIZE,details=True)
    if catalog["state"]!="verified_zip_directory":
        raise ProbeError("Cannot safely inspect official ZIP catalog")
    candidates=[r for r in catalog["entries"] if
                r["name"].startswith("PCB_MC/images/PCB-MC-C/kfold_data/fold_0/") and
                "/labels/" in r["name"] and r["name"].endswith("/"+filename)]
    if len(candidates)!=1:
        raise ProbeError(f"Expected exactly one fold0 candidate; found {len(candidates)}")
    body=read_remote_member(item["download_url"],EXPECTED_SIZE,candidates[0])
    rows=body.decode("utf-8").splitlines()
    from tempfile import TemporaryDirectory
    from pcb_mc_download_fold import _strict_yolo_label
    with TemporaryDirectory() as temp:
        local=Path(temp)/filename
        local.write_bytes(body)
        converted=[]
        class_counts=_strict_yolo_label(local,converted)
        validated=local.read_text(encoding="utf-8").splitlines()
        if len(validated)!=len(rows) or any(len(row.split())!=5 for row in validated if row.strip()):
            raise ProbeError("Real official polygon file could not be normalized to 5-column detection labels")
    target=11
    return {
        "source":"4TU PCB-MC-C public official fold0",
        "file":candidates[0]["name"],
        "total_rows":len(rows),
        "converted_polygon_rows":len(converted),
        "verified_result_row_11":validated[10],
        "verified_capacitor_objects":class_counts["Capacitor"],
        "training_labels_now_detection_boxes":True,
        "row_count_nonstandard_5cols":sum(1 for line in rows if line.strip() and len(line.split())!=5),
        "around_row_11":[
            {"line":i+1,"column_count":len(rows[i].split()),"preview":rows[i][:300]}
            for i in range(max(0,target-4),min(len(rows),target+3))
        ],
        "no_full_archive_download":True,
    }


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--label",required=True)
    ap.add_argument("--out",required=True)
    args=ap.parse_args()
    result=inspect_label(args.label)
    path=Path(args.out)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
