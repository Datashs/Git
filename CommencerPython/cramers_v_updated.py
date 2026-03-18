
from scipy.stats import chi2_contingency
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt

def cramers_v(x, y):
    """Calcul de la corrélation de Cramér's V pour deux séries catégorielles."""
    confusion_matrix = pd.crosstab(x, y)
    chi2 = chi2_contingency(confusion_matrix)[0]
    n = confusion_matrix.sum().sum()
    phi2 = chi2 / n
    r, k = confusion_matrix.shape
    phi2_corr = max(0, phi2 - ((k-1)*(r-1))/(n-1))    
    r_corr = r - ((r-1)**2)/(n-1)
    k_corr = k - ((k-1)**2)/(n-1)
    return np.sqrt(phi2_corr / min((k_corr-1), (r_corr-1)))

# Note: Vous devrez remplacer 'df' par votre DataFrame spécifique.
# df = your_dataframe

# Cette partie du code devrait être adaptée à votre contexte d'utilisation spécifique,
# notamment en définissant 'df' et en manipulant la sélection des colonnes catégorielles comme nécessaire.

# Sélection des colonnes catégorielles (à adapter en fonction de votre DataFrame)
# variables_catégorielles = df.select_dtypes(include=['object']).columns

# Initialisation de la matrice des corrélations de Cramér's V
# cramers_v_matrix = pd.DataFrame(index=variables_catégorielles, columns=variables_catégorielles, dtype=float)

# Calcul de la matrice de corrélation de Cramér's V
# for col1 in variables_catégorielles:
#     for col2 in variables_catégorielles:
#         cramers_v_matrix.loc[col1, col2] = cramers_v(df[col1], df[col2])

# Affichage de la matrice de corrélation de Cramér's V
# print("Matrice de Corrélation de Cramér's V :")
# print(cramers_v_matrix)

# Visualisation de la heatmap
# plt.figure(figsize=(10, 8))
# sns.heatmap(cramers_v_matrix, annot=True, cmap="coolwarm")
# plt.title("Heatmap de Corrélation de Cramér's V")
# plt.show()
