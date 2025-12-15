Exemplo de implementação - Teste T-ESC-10:
pythonimport pytest
import time
from unittest.mock import Mock, patch
from io_communicator import IoCommunicator
from adaptive_chunker import AdaptiveChunker

class TestSyncPerformance:
    """
    Testes derivados do Cenário P1 (Sincronização 30s) - Riscos R6, R13, R28
    Valida tempo total de sincronização e comportamento adaptativo.
    """
    
    @pytest.fixture
    def mock_device(self):
        """Cria mock de dispositivo com latência simulada."""
        device = Mock()
        device.send_cards = Mock(side_effect=lambda cards: time.sleep(0.01 * len(cards) / 100))
        device.is_connected = Mock(return_value=True)
        return device
    
    @pytest.fixture
    def sample_cards(self):
        """Gera lista de 5000 cards para teste."""
        return [
            {
                'id': i,
                'card_number': f'CARD{i:05d}',
                'template': b'x' * 512
            }
            for i in range(5000)
        ]
    
    def test_full_sync_under_30_seconds(self, mock_device, sample_cards):
        """
        T-ESC-10: Sincronização total completa no tempo limite
        
        Cenário ATAM: P1 - Sincronização completa em < 30 segundos
        Riscos: R6 (chunk fixo), R13 (throttling), R28 (timeout)
        Critério: 5000 cards sincronizados em menos de 30 segundos
        """
        # Arrange
        communicator = IoCommunicator(
            chunker=AdaptiveChunker(
                initial_size=500,
                min_size=100,
                max_size=2000
            )
        )
        communicator.register_device('DEV001', mock_device)
        
        # Act: Executar sincronização completa com medição de tempo
        start_time = time.perf_counter()
        
        result = communicator.sync_cards_to_device(
            device_id='DEV001',
            cards=sample_cards,
            timeout=30  # Timeout absoluto
        )
        
        end_time = time.perf_counter()
        elapsed_seconds = end_time - start_time
        
        # Assert
        assert result.success, \
            f"Sincronização falhou: {result.error_message}"
        
        assert elapsed_seconds < 30, \
            f"Sincronização excedeu limite: {elapsed_seconds:.2f}s (máximo: 30s)"
        
        assert result.cards_synced == 5000, \
            f"Sincronização incompleta: {result.cards_synced}/5000 cards"
        
        throughput = 5000 / elapsed_seconds
        print(f"Sincronização concluída em {elapsed_seconds:.2f}s "
              f"(throughput: {throughput:.1f} cards/s)")
    
    def test_timeout_triggers_abort(self, mock_device, sample_cards):
        """
        T-ESC-14: Timeout absoluto previne bloqueio indefinido
        
        Cenário ATAM: P1 - Sincronização completa em < 30 segundos
        Risco: R28 - Ausência de timeout pode bloquear sistema
        Critério: Operação deve abortar após timeout configurado
        """
        # Arrange: Configurar dispositivo lento que excede timeout
        slow_device = Mock()
        slow_device.send_cards = Mock(side_effect=lambda cards: time.sleep(10))
        slow_device.is_connected = Mock(return_value=True)
        
        communicator = IoCommunicator(
            chunker=AdaptiveChunker(initial_size=500)
        )
        communicator.register_device('SLOW_DEV', slow_device)
        
        # Act: Executar com timeout curto
        start_time = time.perf_counter()
        
        result = communicator.sync_cards_to_device(
            device_id='SLOW_DEV',
            cards=sample_cards[:1000],  # Subset menor
            timeout=5  # Timeout de 5 segundos
        )
        
        end_time = time.perf_counter()
        elapsed_seconds = end_time - start_time
        
        # Assert: Operação deve ter sido abortada por timeout
        assert not result.success, \
            "Operação deveria ter falhado por timeout"
        
        assert result.error_code == 'TIMEOUT', \
            f"Erro esperado TIMEOUT, recebido {result.error_code}"
        
        assert elapsed_seconds < 10, \
            f"Timeout não funcionou: operação durou {elapsed_seconds:.2f}s"
        
        print(f"Timeout acionado corretamente após {elapsed_seconds:.2f}s")
