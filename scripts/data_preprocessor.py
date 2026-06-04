import os
import pickle
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

BASE_ML_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ml", "models")

def preprocess_model_1():
    """Preprocess Give Me Some Credit (Model 1)"""
    csv_path = os.path.join(BASE_ML_DIR, "1", "cs-training.csv")
    df = pd.read_csv(csv_path, index_col=0)
    df.rename(columns={"SeriousDlqin2yrs": "target"}, inplace=True)
    df["MonthlyIncome"].fillna(df["MonthlyIncome"].median(), inplace=True)
    df["NumberOfDependents"].fillna(df["NumberOfDependents"].median(), inplace=True)
    df = df[df["age"] > 0]
    df = df[df["RevolvingUtilizationOfUnsecuredLines"] <= 1]
    
    X = df.drop(columns=["target"])
    y = df["target"]
    return X, y

def preprocess_model_2():
    """Preprocess Telco Customer Churn (Model 2)"""
    csv_path = os.path.join(BASE_ML_DIR, "2", "WA_Fn-UseC_-Telco-Customer-Churn.csv")
    df = pd.read_csv(csv_path)
    df.drop(columns=["customerID"], inplace=True)
    df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce")
    df["TotalCharges"].fillna(df["TotalCharges"].median(), inplace=True)
    df["Churn"] = df["Churn"].map({"Yes": 1, "No": 0})
    
    binary_cols = ["Partner", "Dependents", "PhoneService", "PaperlessBilling", "gender"]
    binary_map = {"Yes": 1, "No": 0, "Male": 1, "Female": 0}
    for col in binary_cols:
        df[col] = df[col].map(binary_map)
        
    cat_cols = [
        "MultipleLines", "InternetService", "OnlineSecurity",
        "OnlineBackup", "DeviceProtection", "TechSupport",
        "StreamingTV", "StreamingMovies", "Contract",
        "PaymentMethod"
    ]
    df = pd.get_dummies(df, columns=cat_cols, drop_first=False)
    
    X = df.drop(columns=["Churn"])
    y = df["Churn"]
    return X, y

def preprocess_model_3():
    """Preprocess Online Retail (Model 3)"""
    xlsx_path = os.path.join(BASE_ML_DIR, "3", "online_retail_II.xlsx")
    df1 = pd.read_excel(xlsx_path, sheet_name="Year 2009-2010", engine="openpyxl")
    df2 = pd.read_excel(xlsx_path, sheet_name="Year 2010-2011", engine="openpyxl")
    df = pd.concat([df1, df2], ignore_index=True)
    
    df.dropna(subset=["Customer ID"], inplace=True)
    df = df[~df["Invoice"].astype(str).str.startswith("C")]
    df = df[df["Quantity"] > 0]
    df = df[df["Price"] > 0]
    df["Customer ID"] = df["Customer ID"].astype(int)
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
    
    customer_features = df.groupby("Customer ID").agg(
        customer_total_orders   = ("Invoice", "nunique"),
        customer_total_spent    = ("Price", "sum"),
        customer_avg_order_value= ("Price", "mean"),
        customer_total_items    = ("Quantity", "sum"),
        customer_unique_products= ("StockCode", "nunique")
    ).reset_index()
    
    product_features = df.groupby("StockCode").agg(
        product_total_sold      = ("Quantity", "sum"),
        product_avg_price       = ("Price", "mean"),
        product_unique_customers= ("Customer ID", "nunique")
    ).reset_index()
    
    positives = df[["Customer ID", "StockCode"]].drop_duplicates()
    positives["purchased"] = 1
    
    all_customers = positives["Customer ID"].unique()
    all_products  = positives["StockCode"].unique()
    
    np.random.seed(42)
    neg_customers = np.random.choice(all_customers, size=len(positives), replace=True)
    neg_products  = np.random.choice(all_products,  size=len(positives), replace=True)
    
    negatives = pd.DataFrame({
        "Customer ID": neg_customers,
        "StockCode"  : neg_products,
        "purchased"  : 0
    })
    
    pos_set = set(zip(positives["Customer ID"], positives["StockCode"]))
    mask = [
        (c, s) not in pos_set
        for c, s in zip(negatives["Customer ID"], negatives["StockCode"])
    ]
    negatives = negatives[mask]
    
    data = pd.concat([positives, negatives], ignore_index=True)
    data = data.merge(customer_features, on="Customer ID", how="left")
    data = data.merge(product_features,  on="StockCode",   how="left")
    data.fillna(0, inplace=True)
    
    feature_cols = [
        "customer_total_orders",
        "customer_total_spent",
        "customer_avg_order_value",
        "customer_total_items",
        "customer_unique_products",
        "product_total_sold",
        "product_avg_price",
        "product_unique_customers"
    ]
    
    X = data[feature_cols]
    y = data["purchased"]
    
    X_train, _, _, _ = train_test_split(
        X, y,
        test_size=0.2,
        random_state=42,
        stratify=y
    )
    
    scaler = StandardScaler()
    scaler.fit(X_train)
    return X, y, scaler
