import csv, statistics

def avg_col(rows, *keys):
    for k in keys:
        if k in rows[0]:
            return statistics.mean(float(r[k]) for r in rows)
    raise KeyError(keys)

def load(path):
    with open(path) as f:
        return list(csv.DictReader(f))

B_A = load('/mnt/schemes/Results/CSV-Data/Base-Scheme/auth-results.csv')
B_E = load('/mnt/schemes/Results/CSV-Data/Base-Scheme/enroll-results.csv')
B_K = load('/mnt/schemes/Results/CSV-Data/Base-Scheme/keyex-results.csv')
P_A = load('/mnt/schemes/Results/CSV-Data/Proposed-Scheme-Original/auth-results.csv')
P_E = load('/mnt/schemes/Results/CSV-Data/Proposed-Scheme-Original/enroll-results.csv')
P_K = load('/mnt/schemes/Results/CSV-Data/Proposed-Scheme-Original/keyex-results.csv')
L_A = load('/mnt/schemes/Results/CSV-Data/LAAKA/auth-results.csv')
L_E = load('/mnt/schemes/Results/CSV-Data/LAAKA/enroll-results.csv')
L_K = load('/mnt/schemes/Results/CSV-Data/LAAKA/keyex-results.csv')
Z   = load('/mnt/schemes/Zhou-Scheme/zhou-auth-results.csv')

ec = ('Energy_J','energy_j','Avg_Energy_J')
cc = ('CPU_Time_s','cpu_s','Avg_CPU_s','CPU_s')

b_enr_e, b_enr_c   = avg_col(B_E,*ec), avg_col(B_E,*cc)
b_auth_e, b_auth_c  = avg_col(B_A,*ec), avg_col(B_A,*cc)
b_kex_e, b_kex_c   = avg_col(B_K,*ec), avg_col(B_K,*cc)
b_tot_e  = b_auth_e + b_kex_e
b_tot_c  = b_auth_c + b_kex_c

p_enr_e, p_enr_c   = avg_col(P_E,*ec), avg_col(P_E,*cc)
p_auth_e, p_auth_c  = avg_col(P_A,*ec), avg_col(P_A,*cc)
p_kex_e, p_kex_c   = avg_col(P_K,*ec), avg_col(P_K,*cc)
p_tot_e  = p_auth_e + p_kex_e
p_tot_c  = p_auth_c + p_kex_c

l_enr_e, l_enr_c   = avg_col(L_E,*ec), avg_col(L_E,*cc)
l_auth_e, l_auth_c  = avg_col(L_A,*ec), avg_col(L_A,*cc)
l_kex_e, l_kex_c   = avg_col(L_K,*ec), avg_col(L_K,*cc)
l_tot_e  = l_auth_e + l_kex_e
l_tot_c  = l_auth_c + l_kex_c

z_e = avg_col(Z,'Avg_Energy_J')
z_c = avg_col(Z,'Avg_CPU_s')

def pct(a, b): return (a - b) / b * 100

print("BASE  enroll={:.1f}ms/{:.2f}mJ  auth={:.1f}ms/{:.2f}mJ  kex={:.1f}ms/{:.2f}mJ  tot={:.1f}ms/{:.2f}mJ".format(
    b_enr_c*1e3, b_enr_e*1e3, b_auth_c*1e3, b_auth_e*1e3,
    b_kex_c*1e3, b_kex_e*1e3, b_tot_c*1e3, b_tot_e*1e3))
print("PROP  enroll={:.1f}ms/{:.2f}mJ  auth={:.1f}ms/{:.2f}mJ  kex={:.1f}ms/{:.2f}mJ  tot={:.1f}ms/{:.2f}mJ".format(
    p_enr_c*1e3, p_enr_e*1e3, p_auth_c*1e3, p_auth_e*1e3,
    p_kex_c*1e3, p_kex_e*1e3, p_tot_c*1e3, p_tot_e*1e3))
print("LAAKA enroll={:.1f}ms/{:.2f}mJ  auth={:.1f}ms/{:.2f}mJ  kex={:.1f}ms/{:.2f}mJ  tot={:.1f}ms/{:.2f}mJ".format(
    l_enr_c*1e3, l_enr_e*1e3, l_auth_c*1e3, l_auth_e*1e3,
    l_kex_c*1e3, l_kex_e*1e3, l_tot_c*1e3, l_tot_e*1e3))
print("ZHOU  auth={:.1f}ms/{:.2f}mJ".format(z_c*1e3, z_e*1e3))
print()
print("Proposed vs Base (auth+keyex):  CPU {:+.1f}%  Energy {:+.1f}%".format(pct(p_tot_c,b_tot_c), pct(p_tot_e,b_tot_e)))
print("Proposed vs LAAKA (auth+keyex): CPU {:+.1f}%  Energy {:+.1f}%".format(pct(p_tot_c,l_tot_c), pct(p_tot_e,l_tot_e)))
print("Proposed vs Zhou  (auth):       CPU {:+.1f}%  Energy {:+.1f}%".format(pct(p_tot_c,z_c), pct(p_tot_e,z_e)))
