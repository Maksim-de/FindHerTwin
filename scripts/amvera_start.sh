#!/bin/sh
set -e

cd "$(dirname "$0")/.."

mkdir -p data logs /data/raw /data/processed /data/index /data/metadata

for dir in raw processed index metadata; do
  ln -sfn "/data/$dir" "data/$dir"
done

if [ -f /data/bot.db ]; then
  ln -sfn /data/bot.db data/bot.db
fi

if [ -f /data/metadata/nsfw_labels.json ]; then
  ln -sfn /data/metadata/nsfw_labels.json data/metadata/nsfw_labels.json
fi

exec python -m bot.main
