# TODO tags
from restic_decryptor import *
import argparse
import os
import sys
import json

class PackRef:
    def __init__(self, id):
        self.id = id
        self.fp = None
class Index:
    def __init__(self,basepath,masterkey):
        path = os.path.join(basepath,"index")
        self.basepath = basepath
        self.masterkey =masterkey
        bb={}
        pp={}
        for x in os.listdir(path):
            if len(x) == 64:    
                fp = os.path.join(path,x)
                indexcontent = decrypt_config_index_snapshot(masterkey,fp)
                # dictionary
                #   "packs"
                #       list
                #           dictionary
                #               "id"
                #               "blobs"
                #                   list
                #                       "id"
                #                       "type"
                #                       ...
                for pack in indexcontent["packs"]:
                    pr = PackRef(pack["id"])
                    pp[pr.id] = pr
                    for blob in pack["blobs"]:
                        blob["pack"] = pr
                        bb[blob["id"]] = blob
        self.blobs = bb
        self.packs = pp
    def get(self,id):
        blob = self.blobs.get(id)
        if blob is None:
            return None
        pr = blob["pack"]
        if pr.fp is None:
            pr.fp = open(os.path.join(self.basepath,"data",pr.id[0:2],pr.id),"rb")
        pr.fp.seek(blob["offset"])
        r = decrypt(self.masterkey, pr.fp.read(blob['length']))
        return (blob,r)

def find_path(parts,root,pi):
    blob,t = pi.get(root)
    if t is None:
        return (None,None)
    if blob["type"] != "tree":
        return (None,None)
    t = json.loads(t)
    for n in t["nodes"]:
        if n["name"] == parts[0]:
            if len(parts) == 1:
                return (n,root) # item and parent
            elif n["type"] == "dir":
                return find_path(parts[1:],n["subtree"],pi)
            else:
                break
    return (None,None)
def ls_recursive(root,prefix,pi):
    blob,t = pi.get(root)
    if t is None:
        return
    if blob["type"] != "tree":
        return
    t = json.loads(t)
    for n in t["nodes"]:
        # name
        # type=dir/file
        # content=null if file
        # subtree=reference if dir
        # size if fil
        # extended_attributes
        p = os.path.join(prefix,n["name"])
        if n["type"] == "file":
            print (p)
        elif n["type"] == "dir":
            ls_recursive(n["subtree"],p,pi)
def get_snapshots(repo,masterkey):
    r = []
    bp = os.path.join(repo,"snapshots")
    for x in os.listdir(bp):
        fp = os.path.join(bp,x)
        if os.path.isfile(fp):
            xx = decrypt_config_index_snapshot(masterkey,fp)
            xx["id"] = x[0:8]
            r.append(xx)
    return r

def find_snapshot(snapshotID,args,basepath,masterkey):
    ss = get_snapshots(basepath,masterkey)
    if snapshotID != "latest":
        for snap in ss:
            if snapshotID == snap["id"]:
                return snap
        return None
    else:
        print ("latest not yet implemented")
        return None
def jsonpdumps(x):
    return json.dumps(x,sort_keys=True, indent=4, separators=(',', ': '))
def listfiles(p):
    return [x for x in os.listdir(p) if len(x) == 64]

def path2array(p):
    return p.strip("/").split("/")                


def main():
    objecttype = set("pack|blob|snapshot|index|key|masterkey|config|lock".split("|"))
    listobjectype = set("blobs|packs|index|snapshots|keys|locks".split("|"))
    parser = argparse.ArgumentParser(description='Test decrypt')
    parser.add_argument('-r')
    parser.add_argument('-p')
    parser.add_argument("--json",action="store_true")
    subparsers = parser.add_subparsers(dest="command")
    pcat = subparsers.add_parser('cat')
    pcat.add_argument('type',choices=objecttype)
    pcat.add_argument('ID',default=None)
    plist = subparsers.add_parser('list')
    plist.add_argument('type',choices=listobjectype)

    pls = subparsers.add_parser('ls')
    pls.add_argument('snapshotID')
    pls.add_argument('path')

    pdump = subparsers.add_parser('dump')
    pdump.add_argument('snapshotID')
    pdump.add_argument('path')

    psnapshots = subparsers.add_parser('snapshots')
    pdemo = subparsers.add_parser('demo')

    args = parser.parse_args()


    repo = args.r
    password = args.p
    krepo = os.path.join(repo,"keys")
    drepo = os.path.join(repo,"data")
    keyfile = [x for x in os.listdir(krepo) if os.path.isfile(os.path.join(krepo,x))]
    if len(keyfile) > 1:
        print ("warning: only first key used")
    masterkey = get_masterkey(os.path.join(krepo,keyfile[0]),password)
    if args.command == "demo":
        # decrypt_packfile(masterkey, "repo/data/96/96f1f07...")
        get_all_pack_content_lengths(masterkey, drepo)
    elif args.command == "cat":
        if args.type == "snapshot":
            if not args.ID:
                print ("missing required ID")
            else:
                print (jsonpdumps(decrypt_config_index_snapshot(masterkey,os.path.join(args.r,"snapshots",args.ID))))
        elif args.type == "key":
            if not args.ID:
                print ("missing required ID")
            else:
                print (jsonpdumps(json.load(open(os.path.join(args.r,"keys",args.ID),"rb"))))
        elif args.type == "index":
            if not args.ID:
                print ("missing required ID")
            else:
                print (json.dumps(decrypt_config_index_snapshot(masterkey,os.path.join(args.r,"index",args.ID))))
        elif args.type == "config":
            print (jsonpdumps(decrypt_config_index_snapshot(masterkey,os.path.join(args.r,"snapshots",args.ID))))
        #elif args.type == "masterkey":
        #    print jsonpdumps(dict(mac=dict(k="",p=""),encrypt="")
        elif args.type == "blob":
            pi = Index(args.r,masterkey)
            if not args.ID:
                print ("missing required ID")
            else:
                blob,content = pi.get(args.ID)
                if blob["type"] == "data":
                    print (content)
                else:
                    print (json.loads(content))
        else:
            print ("not implemented type",args.type)
    elif args.command == "snapshots":
        ss = get_snapshots(args.r,masterkey)
        if args.json:
            print (json.dumps(ss))
        else:
            for x in ss:
                print (dict(id=x["id"][0:8],date=x["time"],host=x["hostname"],paths=x["paths"][0]))
        pass
    elif args.command == "ls":
        # find snapshot using args (e.g. filter)
        snap = find_snapshot(args.snapshotID,args,args.r,masterkey)
        if snap is None:
            print ("unknown snapshot")
        else:
            root = snap["tree"]
            pi = Index(args.r,masterkey)
            if args.path is not None and args.path != "/":
                parts = path2array(args.path)             
                node,parent = find_path(parts,root,pi)
                if node is None:
                    print ("missing path",args.path)
                    return
                if node["type"] == "file":
                    print (args.path)
                    return
                else:
                    prefix = "/".join(parts)
                    root = node["subtree"]
            else:
                prefix = "/"
            ls_recursive(root, prefix,pi)
    elif args.command == "dump":
        # find snapshot using args (e.g. filter)
        snap = find_snapshot(args.snapshotID,args,args.r,masterkey)
        if snap is None:
            print ("unknown snapshot")
        else:
            root = snap["tree"]
            pi = Index(args.r,masterkey)
            parts = path2array(args.path)               
            node,parent = find_path(parts,root,pi)
            if node is None:
                print ("missing path",args.path)
                return
            elif node["type"] == "file":
                for c in node["content"]:
                    db,dc = pi.get(c)
                    sys.stdout.buffer.write(dc)
            else:
                blob, content = pi.get(node["subtree"])
                if blob["type"] == "tree":
                    print (json.loads(content)["nodes"])
                else:
                    print ("error")


    elif args.command == "list":
        # [blobs|packs|index|snapshots|keys|locks]
        if args.type == "snapshots":
            print ("\n".join(listfiles(os.path.join(args.r,"snapshots"))))
        elif args.type == "keys":
            print ("\n".join(listfiles(os.path.join(args.r,"keys"))))
        elif args.type == "index":
            print ("\n".join(listfiles(os.path.join(args.r,"index"))))
        elif args.type == "blobs":
            pi = Index(args.r,masterkey)
            for v in pi.blobs.values():
                print (v["type"],v["id"])
        else:
            print ("not implemented type",args.type)


if __name__ == '__main__':
    main()