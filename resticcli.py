# TODO tags
from restic_decryptor import *
import argparse
import os
import json

class PackRef:
    def __init__(self, id):
        self.id = id
        self.fp = None
class Index:
    def __init__(self,basepath,masterkey):
        path = os.path.join(basepath,"index")
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


def get_snapshots(repo,masterkey):
    r = []
    bp = os.path.join(repo,"snapshots")
    for x in os.listdir(bp):
        fp = os.path.join(bp,x)
        if os.path.isfile(fp):
            xx = decrypt_config_index_snapshot(masterkey,fp)
            xx["id"] = x
            r.append(xx)
    return r
def jsonpdumps(x):
    return json.dumps(x,sort_keys=True, indent=4, separators=(',', ': '))
def listfiles(p):
    return [x for x in os.listdir(p) if len(x) == 64]
def main():
    objecttype = set("pack|blob|snapshot|index|key|masterkey|config|lock".split("|"))
    listobjectype = set("blobs|packs|index|snapshots|keys|locks".split("|"))
    parser = argparse.ArgumentParser(description='Test decrypt')
    parser.add_argument('-r')
    parser.add_argument('-p')
    parser.add_argument("--json",action="store_true")
    subparsers = parser.add_subparsers(dest="command")
    pcat = subparsers.add_parser('cat')#, aliases=['co'])
    pcat.add_argument('type',choices=objecttype)#, aliases=['co'])
    pcat.add_argument('ID',default=None)#, aliases=['co'])
    plist = subparsers.add_parser('list')#, aliases=['co'])
    plist.add_argument('type',choices=listobjectype)#, aliases=['co'])
    psnapshots = subparsers.add_parser('snapshots')#, aliases=['co'])
    pdemo = subparsers.add_parser('demo')#, aliases=['co'])

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