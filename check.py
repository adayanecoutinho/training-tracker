"""Testa a conexão com a API do Hevy sem gravar nada."""

import hevy

info = hevy.get("/v1/user/info")
count = hevy.get("/v1/workouts/count")
latest = hevy.get("/v1/workouts", page=1, pageSize=5)

print("Usuário:", info.get("data", info).get("name", "?"))
print("Total de treinos:", count.get("workout_count"))
print("Últimos treinos:")
for w in latest.get("workouts", []):
    print(f"  {w['start_time'][:10]}  {w['title']}  ({len(w.get('exercises', []))} exercícios)")
