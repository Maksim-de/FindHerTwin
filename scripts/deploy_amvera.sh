#!/usr/bin/env bash
# Деплой кода на Amvera через git push.
#
# 1. В панели Amvera: Проект → Репозиторий → скопируйте URL
#    Пример: https://git.amvera.ru/<user>/<project>
# 2. Запуск:
#    AMVERA_GIT_URL='https://git.amvera.ru/user/project' ./scripts/deploy_amvera.sh
#    или: ./scripts/deploy_amvera.sh 'https://git.amvera.ru/user/project'
#
# Логин/пароль — из раздела «Репозиторий» в Amvera (не TELEGRAM_BOT_TOKEN).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

REMOTE="${1:-${AMVERA_GIT_URL:-}}"
if [[ -z "$REMOTE" ]]; then
  if [[ -f .deploy.env ]]; then
    # shellcheck disable=SC1091
    source .deploy.env
    REMOTE="${AMVERA_GIT_URL:-}"
  fi
fi

if [[ -z "$REMOTE" ]]; then
  echo "Ошибка: укажите URL git-репозитория Amvera."
  echo ""
  echo "  AMVERA_GIT_URL='https://git.amvera.ru/USER/PROJECT' ./scripts/deploy_amvera.sh"
  echo "  ./scripts/deploy_amvera.sh 'https://git.amvera.ru/USER/PROJECT'"
  echo ""
  echo "URL берётся в панели Amvera → Проект → Репозиторий."
  exit 1
fi

if [[ ! -d .git ]]; then
  git init
  git branch -M master
fi

chmod +x scripts/amvera_start.sh

git add -A
git status --short

if git diff --cached --quiet; then
  echo "Нет изменений для коммита."
else
  git commit -m "$(cat <<'EOF'
Add Amvera deploy config and Telegram bot.

Deploy code via git; dataset lives on persistent /data storage.
EOF
)"
fi

if git remote get-url amvera &>/dev/null; then
  git remote set-url amvera "$REMOTE"
else
  git remote add amvera "$REMOTE"
fi

echo "Пуш в Amvera: $REMOTE"
git push -u amvera master
