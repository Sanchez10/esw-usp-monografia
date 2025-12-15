# Exemplo de implementação - Teste T-REL-01:

import pytest
import tempfile
import os
from retry_queue import PersistentRetryQueue

class TestRetryQueuePersistence:
    """
    Testes derivados do Cenário D1 (Retry Offline) - Risco R11
    Valida que a fila de retry sobrevive a reinicializações do serviço.
    """
    
    @pytest.fixture
    def db_path(self):
        """Cria arquivo temporário para banco de dados de teste."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.unlink(path)
    
    def test_queue_survives_restart(self, db_path):
        """
        T-REL-01: Fila sobrevive a restart do serviço
        
        Cenário ATAM: D1 - Recuperar de falha de comunicação com device
        Risco: R11 - Chunks falhados são perdidos em restart
        Critério: 100% dos itens devem ser recuperados após restart
        """
        # Arrange: Criar fila e enfileirar operações
        test_items = [
            {'device_id': 'DEV001', 'operation': 'sync_cards', 'payload': {'cards': [1, 2, 3]}},
            {'device_id': 'DEV002', 'operation': 'sync_cards', 'payload': {'cards': [4, 5, 6]}},
            {'device_id': 'DEV003', 'operation': 'sync_faces', 'payload': {'faces': [7, 8, 9]}},
        ]
        
        queue_v1 = PersistentRetryQueue(db_path)
        for item in test_items:
            queue_v1.enqueue(item)
        
        items_before = queue_v1.count()
        queue_v1.close()  # Simula shutdown do serviço
        
        # Act: Recriar fila (simula restart)
        queue_v2 = PersistentRetryQueue(db_path)
        items_after = queue_v2.count()
        recovered_items = [queue_v2.peek(i) for i in range(items_after)]
        
        # Assert: Todos os itens devem estar presentes
        assert items_after == items_before, \
            f"Esperado {items_before} itens, encontrado {items_after}"
        assert items_after == len(test_items), \
            f"Perda de dados: {len(test_items) - items_after} itens perdidos"
        
        # Verificar conteúdo
        for i, original in enumerate(test_items):
            assert recovered_items[i]['device_id'] == original['device_id'], \
                f"Item {i}: device_id divergente"
            assert recovered_items[i]['operation'] == original['operation'], \
                f"Item {i}: operation divergente"
        
        queue_v2.close()
