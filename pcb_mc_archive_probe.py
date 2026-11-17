"""Inspect authoritative PCB-MC metadata and ZIP member names WITHOUT downloading 3.77 GB.

Read-only official 4TU API. Archive header inspection uses byte ranges; if
the host does not support them, report "range_unsupported" instead of
downloading any image data by accident. Never execute source code from ZIP.
"""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path
from urllib.request import Request, urlopen

API = "https://data.4tu.nl/v2"
DOI = "10.4121/7c6e5bda-eecf-4feb-8a3a-7f823b1b0140"
DIRECT_UUID = "7c6e5bda-eecf-4feb-8a3a-7f823b1b0140"
EXPECTED_FILENAME = "PCB_MC.zip"
EXPECTED_SIZE = 3772070324
EXPECTED_MD5 = "1533d1ca6d54c37b19c1a94297c0745c"
MAX_CENTRAL_DIRECTORY = 64 * 1024 * 1024
MAX_ENTRIES = 150000


class ProbeError(RuntimeError):
    pass


def get_json(url, *, post=None):
    payload = json.dumps(post).encode("utf-8") if post is not None else None
    headers = {"User-Agent": "NOVA-DCG-dataset-integrity/1.0"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=payload, headers=headers, method="POST" if post is not None else "GET")
    with urlopen(request, timeout=45) as response:
        if response.status != 200:
            raise ProbeError("Official dataset API did not return HTTP 200")
        data = response.read(3 * 1024 * 1024 + 1)
    if len(data) > 3 * 1024 * 1024:
        raise ProbeError("Official API returned oversized metadata response")
    return json.loads(data)


def select_official_file(articles, files):
    if not isinstance(articles, list) or not articles:
        raise ProbeError("Official 4TU API found no dataset for requested DOI")
    matches = [f for f in files if isinstance(f, dict) and f.get("name") == EXPECTED_FILENAME]
    if len(matches) != 1:
        raise ProbeError("Official archive name missing or ambiguous")
    item = matches[0]
    if item.get("size") != EXPECTED_SIZE:
        raise ProbeError("Official archive size differs from recorded source; re-audit")
    digest = item.get("computed_md5", "")
    if not isinstance(digest, str) or digest.lower() != EXPECTED_MD5:
        raise ProbeError("Official archive MD5 differs from recorded source; re-audit")
    if not isinstance(item.get("download_url"), str) or not item["download_url"].startswith("https://"):
        raise ProbeError("Download URL is not an HTTPS URL")
    return item


def download_range(url, start, end, size):
    if start < 0 or end < start or end >= size:
        raise ProbeError("Invalid range requested")
    requested = end - start + 1
    if requested > MAX_CENTRAL_DIRECTORY:
        raise ProbeError("Archive inspection read too large")
    request = Request(
        url, headers={
            "Range": f"bytes={start}-{end}",
            "User-Agent": "NOVA-DCG-zip-directory-audit/1.0",
            "Accept-Encoding": "identity",
        }
    )
    with urlopen(request, timeout=90) as response:
        if response.status != 206:
            return None
        declared = response.headers.get("Content-Range", "")
        match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", declared)
        if not match or tuple(map(int, match.groups())) != (start,end,size):
            raise ProbeError("Source host returned unexpected byte range")
        body = response.read(requested+1)
    if len(body) != requested:
        raise ProbeError("Archive directory range was truncated")
    return body


def parse_directory(data, expected_entries):
    names=[]
    offset=0
    while offset < len(data):
        if len(names) >= MAX_ENTRIES:
            raise ProbeError("Too many ZIP file entries")
        if data[offset:offset+4] != b"PK\x01\x02":
            raise ProbeError("Invalid ZIP central directory header")
        if offset + 46 > len(data):
            raise ProbeError("Truncated ZIP central directory")
        name_size = struct.unpack_from("<H",data,offset+28)[0]
        extra_size = struct.unpack_from("<H",data,offset+30)[0]
        comment_size = struct.unpack_from("<H",data,offset+32)[0]
        next_offset = offset + 46 + name_size + extra_size + comment_size
        if next_offset > len(data):
            raise ProbeError("Invalid filename length in central directory")
        names.append(data[offset+46:offset+46+name_size].decode("utf-8",errors="replace"))
        offset=next_offset
    if len(names)!=expected_entries:
        raise ProbeError("ZIP central directory count mismatch")
    return names


def read_remote_zip_names(url,size):
    tail_size=min(size,65557)
    tail=download_range(url,size-tail_size,size-1,size)
    if tail is None:
        return {"state":"range_unsupported","entries":[]}
    eocd=tail.rfind(b"PK\x05\x06")
    if eocd < 0 or eocd+22 > len(tail):
        raise ProbeError("ZIP end-of-central-directory not found")
    sig,disk,disk_cd,on_disk,total,cd_size,cd_offset,comment=struct.unpack_from(
        "<4s4H2IH",tail,eocd
    )
    if sig!=b"PK\x05\x06" or disk or disk_cd:
        raise ProbeError(f"Multi-disk ZIP unsupported (disk={disk}, cd_disk={disk_cd})")
    if total==65535 or cd_size==0xffffffff or cd_offset==0xffffffff:
        # Zip64 EOCD Locator precedes the traditional 22-byte EOCD.
        # It holds the uint64 offset of the actual ZIP64 directory record.
        locator_start=eocd-20
        if locator_start < 0 or tail[locator_start:locator_start+4] != b"PK\x06\x07":
            raise ProbeError("ZIP64 locator absent before end-of-central-directory")
        loc_sig,loc_disk,zip64_offset,loc_disks=struct.unpack_from(
            "<4sIQI",tail,locator_start
        )
        if loc_sig!=b"PK\x06\x07" or loc_disk!=0 or loc_disks!=1:
            raise ProbeError("Multi-disk ZIP64 not supported")
        record=download_range(url,zip64_offset,zip64_offset+55,size)
        if record is None:
            return {"state":"range_unsupported","entries":[]}
        sig64,record_size,made,needed,disk64,cd_disk64,one64,total64,size64,offset64=struct.unpack_from(
            "<4sQ2H2I4Q",record,0
        )
        if sig64!=b"PK\x06\x06" or record_size<44 or disk64 or cd_disk64 or one64!=total64:
            raise ProbeError("ZIP64 end-of-directory record inconsistent")
        total,cd_size,cd_offset=total64,size64,offset64
    elif on_disk != total:
        raise ProbeError("ZIP directory entry counts disagree")
    if total>MAX_ENTRIES:
        raise ProbeError(f"Too many archive entries: {total if 'total' in locals() else len(names)}")
    if cd_size > MAX_CENTRAL_DIRECTORY or cd_offset+cd_size>size:
        raise ProbeError("Unusually large central directory; manual review required")
    directory=download_range(url,cd_offset,cd_offset+cd_size-1,size)
    if directory is None:
        return {"state":"range_unsupported","entries":[]}
    names=parse_directory(directory,total)
    return {"state":"verified_zip_directory","entries":names}


def inspect(api=API):
    # 4TU uses UUID article identifiers, not the old Figshare numeric ID.
    # The PCB-MC DOI embeds this exact UUID, so read the official article
    # directly rather than trusting the legacy DOI search endpoint.
    article=get_json(api+"/articles/"+DIRECT_UUID)
    if not isinstance(article,dict):
        raise ProbeError("Official UUID article endpoint returned invalid metadata")
    doi=article.get("doi","")
    title=article.get("title","")
    if not isinstance(doi,str) or not doi.startswith(DOI):
        raise ProbeError("Official article DOI does not match expected PCB-MC source")
    if not isinstance(title,str) or "PCB-MC" not in title:
        raise ProbeError("Official article title does not match source")
    files=get_json(api+"/articles/"+DIRECT_UUID+"/files")
    item=select_official_file([article],files)
    directory=read_remote_zip_names(item["download_url"],EXPECTED_SIZE)
    entries=directory["entries"]
    return {
        "dataset_doi":DOI,
        "source_api":api,
        "archive":{
            "name":item["name"],"bytes":item["size"],"computed_md5":item["computed_md5"],
        },
        "zip_member_probe":directory["state"],
        "zip_entries_count":len(entries),
        "first_fifteen_entries":entries[:15],
        "component_image_count":len([
            name for name in entries
            if name.startswith("PCB_MC/images/PCB-MC-C/") and
               name.lower().endswith((".png",".jpg",".jpeg"))
        ]),
        "component_image_examples":[
            name for name in entries
            if name.startswith("PCB_MC/images/PCB-MC-C/") and
               name.lower().endswith((".png",".jpg",".jpeg"))
        ][:40],
        "component_directory_examples":[
            name for name in entries
            if name.startswith("PCB_MC/images/PCB-MC-C/") and
               name.endswith("/")
        ][:50],
        "pcb_mc_components_annotation_files":[
            name for name in entries if name.startswith("PCB_MC/annotations/PCB-MC-C/") and name.lower().endswith(".json")
        ][:100],
        "pcb_mc_split_files":[
            name for name in entries if name.startswith("PCB_MC/splits/") and name.lower().endswith(".json")
        ][:100],
        "verdict":"metadata_verified_not_training" if not entries else "archive_layout_discovered_not_training",
        "note":"Range inspect does NOT verify the full 3.77GB archive MD5; verify after full download before training.",
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",required=True)
    args=p.parse_args()
    result=inspect()
    dest=Path(args.output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
