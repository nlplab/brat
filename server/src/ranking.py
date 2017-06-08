import pandas as pd
import projectconfig
from document import assert_allowed_to_read
from annlog import real_directory

def get_ranking(collection):
    assert_allowed_to_read(collection)
    dir_name = real_directory(collection)
    log_file = projectconfig.options_get_annlogfile(dir_name)


    if log_file != "<NONE>":
        df = pd.read_csv(log_file,
                         header=None,
                         names=["date", "user", "dir", "document", "event_type", "event_name"],
                         dtype={"dir": str, "document": str},
                         index_col=False,
                         usecols=["user", "dir", "document", "event_name"],
                         sep="\t")

        df = df[df["event_name"] == "createSpan"]

    else:
        df = pd.DataFrame({"user": [], "dir":[], "document":[],  "event_name": []})

    labels = df.groupby("user").count()[["document"]].rename(columns={"document": "annotations"})
    documents = df.drop_duplicates().groupby("user").count().sort_values("document", ascending=False)[["document"]].rename(columns={"document": "documents"})
    ranking = documents.join(labels).head(100)



    return {"users": ranking.reset_index().user.tolist(),
                "total_annotated_docs": documents.sum().tolist()[0] if len(df) > 0 else 0,
                "total_annotations": labels.sum().tolist()[0] if len(df) > 0 else 0,
                "ranking": ranking.reset_index().values.tolist()
            }

