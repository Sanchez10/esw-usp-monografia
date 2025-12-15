# Exemplo de implementação - Teste T-ESC-01:

import pytest
import sqlite3
import tempfile
import time
import os
from database_handler import DatabaseHandler

class TestQueryPerformance:
    """
    Testes derivados do Cenário E1 (Escalabilidade 50k) - Risco R7
    Valida performance da query principal com alto volume de dados.
    """
    
    @pytest.fixture
    def large_db(self):
        """Cria banco de dados com 50k registros para teste de escala."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        conn = sqlite3.connect(path)
        
        # Criar estrutura
        conn.executescript('''
            CREATE TABLE cards (
                id INTEGER PRIMARY KEY,
                card_number TEXT NOT NULL,
                holder_name TEXT,
                department_id INTEGER,
                active INTEGER DEFAULT 1
            );
            
            CREATE TABLE permissions (
                id INTEGER PRIMARY KEY,
                card_id INTEGER,
                controller_id INTEGER,
                access_level INTEGER,
                FOREIGN KEY (card_id) REFERENCES cards(id)
            );
            
            CREATE TABLE faces (
                id INTEGER PRIMARY KEY,
                card_id INTEGER,
                template BLOB,
                FOREIGN KEY (card_id) REFERENCES cards(id)
            );
            
            -- Índices otimizados (mitigação R4)
            CREATE INDEX idx_cards_active ON cards(active);
            CREATE INDEX idx_cards_department ON cards(department_id);
            CREATE INDEX idx_permissions_card ON permissions(card_id);
            CREATE INDEX idx_permissions_controller ON permissions(controller_id);
            CREATE INDEX idx_faces_card ON faces(card_id);
        ''')
        
        # Popular com 50k registros
        print("Populando banco com 50k registros...")
        for i in range(50000):
            conn.execute(
                'INSERT INTO cards (card_number, holder_name, department_id, active) VALUES (?, ?, ?, ?)',
                (f'CARD{i:06d}', f'Holder {i}', i % 100, 1 if i % 10 != 0 else 0)
            )
            conn.execute(
                'INSERT INTO permissions (card_id, controller_id, access_level) VALUES (?, ?, ?)',
                (i + 1, i % 50, i % 5)
            )
            conn.execute(
                'INSERT INTO faces (card_id, template) VALUES (?, ?)',
                (i + 1, b'x' * 1024)  # Template simulado de 1KB
            )
            
            if i % 10000 == 0:
                conn.commit()
                print(f"  {i} registros inseridos...")
        
        conn.commit()
        conn.close()
        print("Banco populado com sucesso.")
        
        yield path
        
        if os.path.exists(path):
            os.unlink(path)
    
    def test_query_50k_under_5_seconds(self, large_db):
        """
        T-ESC-01: Query principal executa em tempo aceitável
        
        Cenário ATAM: E1 - Suportar crescimento de 5k para 50k cards
        Risco: R7 - Query complexa com comportamento O(n²)
        Critério: Tempo de execução < 5000ms para 50k registros
        """
        # Arrange
        db_handler = DatabaseHandler(large_db)
        controller_id = 25  # Controller específico para filtro
        
        # Query principal do sistema (com JOINs)
        query = '''
            SELECT c.id, c.card_number, c.holder_name, 
                   p.access_level, f.template
            FROM cards c
            INNER JOIN permissions p ON c.id = p.card_id
            INNER JOIN faces f ON c.id = f.card_id
            WHERE c.active = 1 
              AND p.controller_id = ?
        '''
        
        # Act: Medir tempo de execução
        start_time = time.perf_counter()
        results = db_handler.execute_query(query, (controller_id,))
        end_time = time.perf_counter()
        
        elapsed_ms = (end_time - start_time) * 1000
        
        # Assert
        assert elapsed_ms < 5000, \
            f"Query excedeu limite: {elapsed_ms:.2f}ms (máximo: 5000ms)"
        
        assert len(results) > 0, \
            "Query não retornou resultados - verificar dados de teste"
        
        print(f"Query executada em {elapsed_ms:.2f}ms, "
              f"retornando {len(results)} registros")
        
        db_handler.close()
    
    def test_query_uses_indexes(self, large_db):
        """
        T-ESC-02: Índices são utilizados pelo query planner
        
        Cenário ATAM: E1 - Suportar crescimento de 5k para 50k cards
        Risco: R4 - Query não utiliza índices adequadamente
        Critério: EXPLAIN QUERY PLAN deve mostrar uso de INDEX
        """
        # Arrange
        conn = sqlite3.connect(large_db)
        
        query = '''
            EXPLAIN QUERY PLAN
            SELECT c.id, c.card_number, p.access_level
            FROM cards c
            INNER JOIN permissions p ON c.id = p.card_id
            WHERE c.active = 1 
              AND p.controller_id = 25
        '''
        
        # Act
        cursor = conn.execute(query)
        plan = cursor.fetchall()
        plan_text = ' '.join([str(row) for row in plan])
        
        # Assert: Verificar uso de índices
        uses_index = 'INDEX' in plan_text or 'USING' in plan_text
        no_full_scan = 'SCAN TABLE' not in plan_text or 'USING' in plan_text
        
        assert uses_index, \
            f"Query não utiliza índices. Plano: {plan_text}"
        
        print(f"Query plan: {plan_text}")
        
        conn.close()
