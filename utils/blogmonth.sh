python ../utils/blog_arch.py -b https://soldersmoke.blogspot.com/ $1 $2 -o soldertest 
git config pull.rebase true
git pull
git add soldertest
git commit -m"more posts"
git push origin main

