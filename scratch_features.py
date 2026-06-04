import pickle
import os

base_dir = r"c:\Users\debnil\projects\Sentinel\ml\models"
for i in [1, 2, 3]:
    path = os.path.join(base_dir, str(i), "feature_names.pkl")
    if os.path.exists(path):
        with open(path, "rb") as f:
            features = pickle.load(f)
        print(f"Model {i} Features:", features)
    else:
        print(f"Model {i} features file not found.")
