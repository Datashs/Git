def cramers_v(x, y):
   # nous utilions une Magic command (c'est officiellement son nom) des carnets jupyter pour créer une fonction externe
    # Elle pourra être importée et utilisée dans n'importe quel carnet 


#Il existe des fonctions dans certaines bibliothèques permettant le calcul de Cramer_V 
    # les utiliser nous contraindrait à importer une autre bibliothèque pour un usage unique, ce qu'il est de bonne pratique d'éviter
    # Et surtout nous n'aurions pas l'occasion de donner un exemple de création de fonction. 

from scipy.stats import chi2_contingency

    """Calcul de la corrélation de Cramér's V pour deux séries catégorielles."""
    confusion_matrix = pd.crosstab(x, y)
    chi2 = chi2_contingency(confusion_matrix, correction=False)[0]
# Par correction = false nous demandons explicitement de ne pas appliquer la correction de Yates

    n = confusion_matrix.sum().sum()
    phi2 = chi2 / n
    r, k = confusion_matrix.shape
    phi2_corr = max(0, phi2 - ((k-1)*(r-1))/(n-1))    
    r_corr = r - ((r-1)**2)/(n-1)
    k_corr = k - ((k-1)**2)/(n-1)
    return np.sqrt(phi2_corr / min((k_corr-1), (r_corr-1)))


