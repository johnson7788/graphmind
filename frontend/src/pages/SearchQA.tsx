import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Input,
  Radio,
  Card,
  Select,
  Timeline,
  Typography,
  Empty,
  Button,
  Space,
  message,
  Tag,
  Divider,
  Row,
  Col,
  Alert,
} from 'antd';
import {
  SearchOutlined,
  DeleteOutlined,
  ClockCircleOutlined,
  GlobalOutlined,
  FileSearchOutlined,
  BulbOutlined,
  LoadingOutlined,
  StopOutlined,
  DeploymentUnitOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useDatasetStore } from '../stores/datasetStore';
import { useSearchStore } from '../stores/searchStore';
import { searchKnowledgeStream } from '../services/api';

const { Title, Text, Paragraph } = Typography;

const modeConfig: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  mix: { label: '混合检索', color: 'purple', icon: <DeploymentUnitOutlined /> },
  local: { label: '本地搜索', color: 'blue', icon: <FileSearchOutlined /> },
  global: { label: '全局搜索', color: 'green', icon: <GlobalOutlined /> },
  hybrid: { label: '混合模式', color: 'cyan', icon: <ThunderboltOutlined /> },
  naive: { label: '基础 RAG', color: 'orange', icon: <BulbOutlined /> },
};

export default function SearchQA() {
  const { datasets, selectedId, selectDataset, fetchDatasets } = useDatasetStore();
  const {
    results,
    currentResult,
    streaming,
    addResult,
    setCurrentResult,
    appendAnswerChunk,
    setStreaming,
    clearHistory,
  } = useSearchStore();

  const [mode, setMode] = useState<string>('mix');
  const [queryValue, setQueryValue] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    fetchDatasets();
  }, [fetchDatasets]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const handleCancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setStreaming(false);
    setStatusMessage('');
  }, [setStreaming]);

  const handleSearch = useCallback(
    (query: string) => {
      if (!query.trim()) {
        message.warning('请输入搜索问题');
        return;
      }
      if (!selectedId) {
        message.warning('请先选择数据集');
        return;
      }

      // Cancel any in-flight request
      abortRef.current?.abort();

      setStreaming(true);
      setStatusMessage('正在准备...');
      setCurrentResult({
        query: query.trim(),
        mode,
        answer: '',
        time: new Date().toLocaleTimeString(),
      });
      setQueryValue('');

      const trimmedQuery = query.trim();

      abortRef.current = searchKnowledgeStream(selectedId, trimmedQuery, mode, {
        onStatus: (_status, msg) => {
          setStatusMessage(msg);
        },
        onChunk: (text) => {
          appendAnswerChunk(text);
        },
        onDone: (data) => {
          const finalResult = {
            query: data.query,
            mode: data.mode,
            answer: data.answer,
            time: new Date().toLocaleTimeString(),
          };
          addResult(finalResult);
          setCurrentResult(finalResult);
          setStreaming(false);
          setStatusMessage('');
          abortRef.current = null;
        },
        onError: (msg) => {
          setCurrentResult({
            query: trimmedQuery,
            mode,
            answer: msg,
            time: new Date().toLocaleTimeString(),
          });
          setStreaming(false);
          setStatusMessage('');
          abortRef.current = null;
        },
      });
    },
    [selectedId, mode, setStreaming, setCurrentResult, appendAnswerChunk, addResult],
  );

  const handleClearHistory = () => {
    clearHistory();
    message.success('搜索历史已清空');
  };

  const handleHistoryClick = (result: typeof currentResult) => {
    if (result && !streaming) setCurrentResult(result);
  };

  const selectedDataset = datasets.find((d) => d.id === selectedId);

  // -- No dataset selected state --
  if (!selectedId) {
    return (
      <div>
        <Title level={4}>智能问答</Title>
        <Divider />
        <div style={{ marginBottom: 24 }}>
          <Text strong style={{ marginRight: 12 }}>
            选择数据集：
          </Text>
          <Select
            placeholder="请选择数据集"
            style={{ width: 320 }}
            loading={useDatasetStore.getState().loading}
            onChange={(val) => selectDataset(val)}
            options={datasets.map((d) => ({
              label: `${d.name}${d.has_index ? '' : ' (未索引)'}`,
              value: d.id,
              disabled: !d.has_index,
            }))}
          />
        </div>
        <Empty description="请先选择一个已索引的数据集" />
      </div>
    );
  }

  const hasAnswer = currentResult && currentResult.answer.length > 0;

  return (
    <div>
      <Title level={4}>智能问答</Title>
      <Divider />

      {/* Dataset Selector */}
      <div style={{ marginBottom: 24 }}>
        <Text strong style={{ marginRight: 12 }}>
          当前数据集：
        </Text>
        <Select
          value={selectedId}
          style={{ width: 320 }}
          onChange={(val) => {
            selectDataset(val);
            setCurrentResult(null);
          }}
          options={datasets.map((d) => ({
            label: `${d.name}${d.has_index ? '' : ' (未索引)'}`,
            value: d.id,
            disabled: !d.has_index,
          }))}
        />
        {selectedDataset && (
          <Text type="secondary" style={{ marginLeft: 12 }}>
            实体: {selectedDataset.entity_count} | 关系: {selectedDataset.relationship_count}
          </Text>
        )}
      </div>

      {/* Search Mode */}
      <div style={{ marginBottom: 16 }}>
        <Text strong style={{ marginRight: 12 }}>
          搜索模式：
        </Text>
        <Radio.Group
          value={mode}
          onChange={(e) => setMode(e.target.value)}
          disabled={streaming}
        >
          {Object.entries(modeConfig).map(([key, cfg]) => (
            <Radio.Button key={key} value={key}>
              {cfg.icon} {cfg.label}
            </Radio.Button>
          ))}
        </Radio.Group>
      </div>

      {/* Search Input */}
      <div style={{ marginBottom: 24 }}>
        <Input.Search
          value={queryValue}
          onChange={(e) => setQueryValue(e.target.value)}
          placeholder="请输入问题"
          enterButton={
            <span>
              <SearchOutlined /> 搜索
            </span>
          }
          size="large"
          loading={streaming}
          onSearch={handleSearch}
          disabled={streaming}
        />
      </div>

      {/* Status banner during streaming */}
      {streaming && (
        <Alert
          type="info"
          showIcon
          icon={<LoadingOutlined />}
          message={statusMessage || '正在搜索中...'}
          action={
            <Button size="small" type="text" icon={<StopOutlined />} onClick={handleCancel}>
              取消
            </Button>
          }
          style={{ marginBottom: 16 }}
        />
      )}

      {/* Result + History layout */}
      <Row gutter={24}>
        {/* Result Panel */}
        <Col xs={24} lg={16}>
          {currentResult ? (
            <Card
              title={
                <Space>
                  <Tag color={modeConfig[currentResult.mode]?.color}>
                    {modeConfig[currentResult.mode]?.label || currentResult.mode}
                  </Tag>
                  <Text type="secondary">
                    <ClockCircleOutlined style={{ marginRight: 4 }} />
                    {currentResult.time}
                  </Text>
                  {streaming && <LoadingOutlined style={{ color: '#1677ff' }} />}
                </Space>
              }
              extra={
                !streaming && (
                  <Button size="small" type="text" onClick={() => setCurrentResult(null)}>
                    关闭
                  </Button>
                )
              }
            >
              <div style={{ marginBottom: 12 }}>
                <Text strong>问题：</Text>
                <Text>{currentResult.query}</Text>
              </div>
              <Divider style={{ margin: '12px 0' }} />
              {hasAnswer ? (
                <div className="markdown-body" style={{ fontSize: 14, lineHeight: 1.8 }}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {currentResult.answer}
                  </ReactMarkdown>
                </div>
              ) : (
                !streaming && (
                  <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description="搜索出错"
                  />
                )
              )}
            </Card>
          ) : (
            <Card>
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="输入问题开始搜索"
              />
            </Card>
          )}
        </Col>

        {/* History Panel */}
        <Col xs={24} lg={8}>
          <Card
            title={
              <Space>
                <ClockCircleOutlined />
                <span>搜索历史</span>
                <Tag>{results.length}</Tag>
              </Space>
            }
            extra={
              results.length > 0 && (
                <Button
                  size="small"
                  type="text"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={handleClearHistory}
                >
                  清空
                </Button>
              )
            }
          >
            {results.length > 0 ? (
              <Timeline
                items={results.map((r, idx) => ({
                  key: idx,
                  children: (
                    <div
                      style={{
                        cursor: streaming ? 'default' : 'pointer',
                        opacity: streaming ? 0.6 : 1,
                      }}
                      onClick={() => handleHistoryClick(r)}
                    >
                      <Space>
                        <Tag color={modeConfig[r.mode]?.color} style={{ fontSize: 11 }}>
                          {modeConfig[r.mode]?.label || r.mode}
                        </Tag>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {r.time}
                        </Text>
                      </Space>
                      <Paragraph
                        ellipsis={{ rows: 2 }}
                        style={{ marginBottom: 0, marginTop: 4, fontSize: 13 }}
                      >
                        {r.query}
                      </Paragraph>
                    </div>
                  ),
                }))}
              />
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无搜索历史" />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
