# Exemplo de implementação - Teste T-REL-12:

import pytest
import sqlite3
import tempfile
import os
from backup_manager import BackupManager

class TestBackupIntegrity:
    """
    Testes derivados do Cenário C1 (Atomicidade) - Riscos R15, R16
    Valida integridade dos backups criados automaticamente.
    """
    
    @pytest.fixture
    def populated_db(self):
        """Cria banco de dados populado para teste."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        conn = sqlite3.connect(path)
        conn.execute('''
            CREATE TABLE cards (
                id INTEGER PRIMARY KEY,
                card_number TEXT NOT NULL,
                holder_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Inserir dados de teste
        for i in range(1500):  # > 1000 para disparar backup
            conn.execute(
                'INSERT INTO cards (card_number, holder_name) VALUES (?, ?)',
                (f'CARD{i:05d}', f'Holder {i}')
            )
        conn.commit()
        conn.close()
        
        yield path
        
        # Cleanup
        for f in [path, f"{path}.bak"]:
            if os.path.exists(f):
                os.unlink(f)
    
    def test_backup_integrity_check(self, populated_db):
        """
        T-REL-12: Integridade do backup é verificável
        
        Cenário ATAM: C1 - Bulk insert com atomicidade
        Riscos: R15 (corrupção), R16 (integridade)
        Critério: PRAGMA integrity_check deve retornar 'ok'
        """
        # Arrange: Criar backup
        backup_manager = BackupManager(populated_db)
        backup_path = backup_manager.create_backup()
        
        assert os.path.exists(backup_path), "Backup não foi criado"
        
        # Act: Verificar integridade do backup
        conn = sqlite3.connect(backup_path)
        cursor = conn.execute('PRAGMA integrity_check')
        result = cursor.fetchone()[0]
        conn.close()
        
        # Assert: Integridade deve estar ok
        assert result == 'ok', \
            f"Falha de integridade no backup: {result}"
        
        # Verificar que dados estão presentes
        conn = sqlite3.connect(backup_path)
        cursor = conn.execute('SELECT COUNT(*) FROM cards')
        count = cursor.fetchone()[0]
        conn.close()
        
        assert count == 1500, \
            f"Backup incompleto: esperado 1500 registros, encontrado {count}"
