import numpy as np
from sklearn.cluster import DBSCAN, KMeans


def make_clusters_dbscan(images, eps=3) -> list[list[str]]:
    res = []
    vectors, sha1 = zip(*[(i.vector, i.sha1) for i in images])
    clusters = DBSCAN(eps=eps).fit(np.asarray(vectors))
    for cluster in list(set(clusters.labels_)):
        sha1_clusters = np.asarray(sha1)[clusters.labels_ == cluster]
        res.append(list(sha1_clusters))
    return res


def make_clusters(images, nb_clusters=6) -> list[list[str]]:
    res = []
    vectors, sha1 = zip(*[(i.vector, i.sha1) for i in images])
    clusters = KMeans(n_clusters=int(nb_clusters)).fit_predict(vectors)
    for cluster in list(set(clusters)):
        sha1_clusters = np.asarray(sha1)[clusters == cluster]
        res.append(list(sha1_clusters))
    return res