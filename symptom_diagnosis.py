# symptom_diagnosis.py

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report
import joblib

# Load dataset
data = pd.read_csv("symptoms_faults.csv")

# Split data
X_train, X_test, y_train, y_test = train_test_split(
    data["symptom"], data["probable_fault"], test_size=0.2, random_state=42
)

# Create a pipeline: TF-IDF vectorizer + classifier
model = Pipeline([
    ("tfidf", TfidfVectorizer()),
    ("clf", MultinomialNB())
])

# Train the model
model.fit(X_train, y_train)

# Evaluate
y_pred = model.predict(X_test)
print(classification_report(y_test, y_pred))

# Save model
joblib.dump(model, "diagnosis_model.pkl")

# --- Test it manually ---
def diagnose(symptom):
    return model.predict([symptom])[0]

# Example test
print("Diagnosis:", diagnose("car makes a squealing noise when braking"))
