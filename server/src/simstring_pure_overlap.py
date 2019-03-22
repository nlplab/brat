from simstring.measure.base import BaseMeasure
from sys import maxsize
import math

class OverlapMeasure(BaseMeasure):
    def min_feature_size(self, query_size, alpha):
        return 1

    def max_feature_size(self, query_size, alpha):
        return maxsize

    def minimum_common_feature_count(self, query_size, y_size, alpha):
        return int(math.ceil(alpha * min(query_size, y_size)))

    def similarity(self, X, Y):
        return min(len(set(X)), len(set(Y)))


def patch_search(self, query_string, alpha):
    features = self.feature_extractor.features(query_string)
    min_feature_size = self.measure.min_feature_size(len(features), alpha)
    max_feature_size = self.measure.max_feature_size(len(features), alpha)
    # -- PATCH START
    max_feature_size = min(max_feature_size, self.db.max_feature_size())
    # -- PATCH END
    results = []

    for candidate_feature_size in range(min_feature_size, max_feature_size + 1):
        tau = self._Searcher__min_overlap(len(features), candidate_feature_size, alpha)
        results.extend(self._Searcher__overlap_join(features, tau, candidate_feature_size))

    return results

from simstring.searcher import Searcher
Searcher.search = patch_search
