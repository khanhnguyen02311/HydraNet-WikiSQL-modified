import argparse
import os
import json
import pickle
import utils
from modeling.model_factory import create_model
from featurizer import HydraFeaturizer, SQLDataset
from wikisql_lib.dbengine import DBEngine


parser = argparse.ArgumentParser(description='HydraNet prediction scrpit')
parser.add_argument("--output_path", type=str, default="output", help="current output folder path")
parser.add_argument("--checkpoint_time", type=str, help="checkpoint time of the model")
parser.add_argument("--epoch", type=int, default=1, help="model epoch that you want to get result")
parser.add_argument("--dataset_type", type=str, default="test", help="evaluation on ['dev', 'test']")

args = parser.parse_args()


def print_metric(label_file, pred_file):
    sp = [(json.loads(ls)["sql"], json.loads(lp)["query"]) for ls, lp in zip(open(label_file), open(pred_file))]

    sel_acc = sum(p["sel"] == s["sel"] for s, p in sp) / len(sp)
    agg_acc = sum(p["agg"] == s["agg"] for s, p in sp) / len(sp)
    wcn_acc = sum(len(p["conds"]) == len(s["conds"]) for s, p in sp) / len(sp)

    def wcc_match(a, b):
        a = sorted(a, key=lambda k: k[0])
        b = sorted(b, key=lambda k: k[0])
        return [c[0] for c in a] == [c[0] for c in b]

    def wco_match(a, b):
        a = sorted(a, key=lambda k: k[0])
        b = sorted(b, key=lambda k: k[0])
        return [c[1] for c in a] == [c[1] for c in b]

    def wcv_match(a, b):
        a = sorted(a, key=lambda k: k[0])
        b = sorted(b, key=lambda k: k[0])
        return [str(c[2]).lower() for c in a] == [str(c[2]).lower() for c in b]

    wcc_acc = sum(wcc_match(p["conds"], s["conds"]) for s, p in sp) / len(sp)
    wco_acc = sum(wco_match(p["conds"], s["conds"]) for s, p in sp) / len(sp)
    wcv_acc = sum(wcv_match(p["conds"], s["conds"]) for s, p in sp) / len(sp)

    print('sel_acc: {}\nagg_acc: {}\nwcn_acc: {}\nwcc_acc: {}\nwco_acc: {}\nwcv_acc: {}\n' \
          .format(sel_acc, agg_acc, wcn_acc, wcc_acc, wco_acc, wcv_acc))


if __name__ == "__main__":
    # in_file = "data/wikidev.jsonl"
    # out_file = "output/dev_out.jsonl"
    # label_file = "WikiSQL/data/dev.jsonl"
    # db_file = "WikiSQL/data/dev.db"
    # model_out_file = "output/dev_model_out.pkl"
    
    in_file = f"data/wiki{args.dataset_type}.jsonl"
    label_file = f"WikiSQL/data/{args.dataset_type}.jsonl"
    db_file = f"WikiSQL/data/{args.dataset_type}.db"
    
    out_file = os.path.join(args.output_path, args.checkpoint_time, f"{args.dataset_type}_out_{args.epoch}.jsonl")
    model_out_file = os.path.join(args.output_path, args.checkpoint_time, f"{args.dataset_type}_model_out_{args.epoch}.pkl")

    # All Best
    model_path = os.path.join(args.output_path, args.checkpoint_time)
    epoch = args.epoch

    engine = DBEngine(db_file)
    config = utils.read_conf(os.path.join(model_path, "model.conf"))
    # config["DEBUG"] = 1
    featurizer = HydraFeaturizer(config)
    pred_data = SQLDataset(in_file, config, featurizer, False)
    print("num of samples: {0}".format(len(pred_data.input_features)))

    model = create_model(config, is_train=False)
    model.load(model_path, epoch)

    if "DEBUG" in config:
        model_out_file = model_out_file + ".partial"

    if os.path.exists(model_out_file):
        model_outputs = pickle.load(open(model_out_file, "rb"))
    else:
        model_outputs = model.dataset_inference(pred_data)
        pickle.dump(model_outputs, open(model_out_file, "wb"))

    print("===HydraNet===")
    pred_sqls = model.predict_SQL(pred_data, model_outputs=model_outputs)
    with open(out_file, "w") as g:
        for pred_sql in pred_sqls:
            # print(pred_sql)
            result = {"query": {}}
            result["query"]["agg"] = int(pred_sql[0])
            result["query"]["sel"] = int(pred_sql[1])
            result["query"]["conds"] = [(int(cond[0]), int(cond[1]), str(cond[2])) for cond in pred_sql[2]]
            g.write(json.dumps(result) + "\n")
    print_metric(label_file, out_file)

    print("===HydraNet+EG===")
    pred_sqls = model.predict_SQL_with_EG(engine, pred_data, model_outputs=model_outputs)
    with open(out_file + ".eg", "w") as g:
        for pred_sql in pred_sqls:
            # print(pred_sql)
            result = {"query": {}}
            result["query"]["agg"] = int(pred_sql[0])
            result["query"]["sel"] = int(pred_sql[1])
            result["query"]["conds"] = [(int(cond[0]), int(cond[1]), str(cond[2])) for cond in pred_sql[2]]
            g.write(json.dumps(result) + "\n")
    print_metric(label_file, out_file + ".eg")
