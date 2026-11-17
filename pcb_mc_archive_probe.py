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
EXPECTED_FILENAME = "PCB_MC.zip"
EXPECTED_SIZE = 3772070324
EXPECTED_MD5 = "1533d1ca6d54c37b19c1a94297c0745c"
MAX_CENTRAL_DIRECTORY = 12 * 1024 * 1024
MAX_ENTRIES = 25000


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
    if sig!=b"PK\x05\x06" or disk or disk_cd or on_disk!=total or total>MAX_ENTRIES:
        raise ProbeError("Multi-disk or invalid ZIP directory not supported")
    if cd_size > MAX_CENTRAL_DIRECTORY or cd_offset+cd_size>size:
        raise ProbeError("Unusually large central directory; manual review required")
    if total==65535 or cd_size==0xffffffff or cd_offset==0xffffffff:
        raise ProbeError("ZIP64 central directory requires manual inspection")
    directory=download_range(url,cd_offset,cd_offset+cd_size-1,size)
    if directory is None:
        return {"state":"range_unsupported","entries":[]}
    names=parse_directory(directory,total)
    return {"state":"verified_zip_directory","entries":names}


def inspect(api=API):
    articles=get_json(api+"/articles/search",post={"doi":DOI})
    article=articles[0]
    if not isinstance(article.get("id"),int):
        raise ProbeError("Official API returned no numeric article identifier")
    files=get_json(api+f"/articles/{article['id']}/files")
    item=select_official_file(articles,files)
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
        "pcb_mc_components_annotation_files":[
            name for name in entries if "/annotations/PCB-MC-C/" in "/"+name and name.lower().endswith(".json")
        ][:100],
        "pcb_mc_split_files":[
            name for name in entries if "/splits/" in "/"+name and name.lower().endswith(".json")
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
