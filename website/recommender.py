import pandas as pd
from website.models import Avaliacao, Loja, Cliente
import numpy as np


class Recommender:

    def __init__(self):
        self.pred = None
        self.is_fitted = False

    def load_rating(self):
        qs = Avaliacao.objects.all().values_list('cliente_id', 'loja_id', 'rating')
        return pd.DataFrame(
            qs, columns=['cliente_id', 'loja_id', 'rating'])

    def create_ratings_u_i(self, df_ratings):
        n_users = Cliente.objects.count()
        n_items = Loja.objects.count()
        ratings = np.zeros((n_users, n_items))

        for row in df_ratings.itertuples():
            ratings[row[1]-1, row[2]-1] = row[3]
        return ratings

    def compute_similarity(self, ratings, epsilon=1e-9):
        sim = ratings.dot(ratings.T) + epsilon
        norms = np.array([np.sqrt(np.diagonal(sim))])
        similarity = (sim / norms / norms.T)
        return similarity

    def compute_pred(self, ratings, similarity, k=20):
        self.pred = np.zeros(ratings.shape)
        for i in range(0, ratings.shape[0]):
            top_k_users = [np.argsort(similarity[:, i])[:-k-1:-1]]
            for j in range(0, ratings.shape[1]):
                self.pred[i, j] = similarity[i, :][tuple(top_k_users)].dot(
                    ratings[:, j][tuple(top_k_users)])
                self.pred[i,
                          j] /= np.sum(np.abs(similarity[i, :][tuple(top_k_users)]))

    def fit(self):
        df_ratings = self.load_rating()
        ratings = self.create_ratings_u_i(df_ratings)
        similarity = self.compute_similarity(ratings)
        self.compute_pred(ratings, similarity)
        self.is_fitted = True

    def get_topk_lojas(self, userId, k=5):
        return np.argsort(self.pred[userId-1, :])[:-k-1:-1] + 1


recommender = Recommender()
recommender.fit()
