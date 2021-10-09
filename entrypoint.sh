#!/bin/sh -l
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