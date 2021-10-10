#!/bin/bash
PUSH=0
python3 ${PROCESS_ICAL_PATH} ${INPUT_DAYS} &
mkdir -p public && echo ${RUN_NUMBER} > public/index.html
[ -n "${COMPARE_URL}" ] && { wget -q "${COMPARE_URL}" -O prev.tsv || PUSH=1; }
wait
[ ${PUSH} = 0 ] && diff -q -s prev.tsv public/pruned.tsv && exit 0 || true
cd public
# based on https://github.com/BryanSchuetz/jekyll-deploy-gh-pages/blob/master/entrypoint.sh
remote_repo="https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" && \
git init -b gh-pages && \
git config user.name "${GITHUB_ACTOR} [actions]" && \
git config user.email "${GITHUB_ACTOR}@users.noreply.github.com" && \
git add . && \
git commit -m'Update pages' > /dev/null 2>&1 && \
git push --force $remote_repo gh-pages:gh-pages > /dev/null 2>&1 && \
rm -fr .git
