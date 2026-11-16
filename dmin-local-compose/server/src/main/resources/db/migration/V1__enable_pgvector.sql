-- CA 문서 임베딩(CMP-11)은 pgvector 열에 둔다 (D-MIN-server V1과 같다). RDS for PostgreSQL 17도 pgvector를 지원한다.
CREATE EXTENSION IF NOT EXISTS vector;
