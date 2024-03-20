

from scipy.stats import chi2_contingency
import pandas as pd 
import numpy as np
  
# nous utilions une Magic command (c'est officiellement son nom) des carnets jupyter pour créer une fonction externe
 # Elle pourra être importée et utilisée dans n'importe quel carnet
# Il existe des fonctions dans certaines bibliothèques permettant le calcul de Cramer_V
# Les utiliser nous contraindrait à importer une autre bibliothèque pour un usage unique, ce qu'il est de bonne pratique d'éviter
# Et surtout nous n'aurions pas l'occasion de donner un exemple de création de fonction

def cramers_v(x, y):


   """
   Calcul de la corrélation de Cramér's V pour deux séries catégorielles.
   - x, y : séries pandas catégorielles.
   
   Retourne la corrélation de Cramér's V entre x et y, sans appliquer la correction de Yates.
   """
   # Création d'une matrice de contingence
   confusion_matrix = pd.crosstab(x, y)
   # Calcul de la statistique Chi2 sans correction de Yates
   chi2 = chi2_contingency(confusion_matrix, correction=False)[0]
   
   # Nombre total d'observations
   n = confusion_matrix.sum().sum()
   # Calcul de phi2
   phi2 = chi2 / n
   # Nombre de lignes et de colonnes dans la matrice de contingence
   r, k = confusion_matrix.shape
   # Correction de phi2 pour les tailles des tableaux de contingence
   phi2_corr = max(0, phi2 - ((k-1)*(r-1))/(n-1))    
   # Corrections pour les degrés de liberté ajustés
   r_corr = r - ((r-1)**2)/(n-1)
   k_corr = k - ((k-1)**2)/(n-1)
   # Calcul et retour du coefficient de Cramér's V
   return np.sqrt(phi2_corr / min((k_corr-1), (r_corr-1)))

