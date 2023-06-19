from collections import namedtuple

# simirarity queryの結果型
GithubDocument = namedtuple('Document', ['title', 'url', 'comments', 'state', 'labels', 'created_at'])
