import sqlite3
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib

def train_model():
    con = sqlite3.connect("task.db")

    df = pd.read_sql_query("""
        SELECT 
            julianday(to_date) - julianday(from_date) AS duration,
            earned_coins,
            CASE WHEN completed_date > to_date THEN 1 ELSE 0 END AS delayed
        FROM adds__task
        WHERE status='completed'
    """, con)

    con.close()
    X = df[['duration', 'earned_coins']]
    y = df['delayed']
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    model = LogisticRegression()
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print("Model Accuracy:", acc * 100, "%")
    print("\nClassification Report:\n", classification_report(y_test, y_pred))
    joblib.dump(model, "delay_predictor.pkl")
if __name__ == "__main__":
    train_model()