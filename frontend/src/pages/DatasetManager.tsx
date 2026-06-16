import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  Row,
  Col,
  Card,
  Input,
  Upload,
  type UploadFile,
  Button,
  Select,
  List,
  Tag,
  Steps,
  Progress,
  Alert,
  Spin,
  Typography,
  Space,
  Popconfirm,
  Tabs,
  message,
} from 'antd';
import {
  InboxOutlined,
  DeleteOutlined,
  DatabaseOutlined,
  ThunderboltOutlined,
  ClockCircleOutlined,
  ExperimentOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  FileTextOutlined,
  SettingOutlined,
  RocketOutlined,
  ArrowLeftOutlined,
  ArrowRightOutlined,
  CloseCircleFilled,
} from '@ant-design/icons';
import {
  createDataset,
  uploadDocuments,
  startIndexing,
  discoverEntityTypes,
  deleteDataset,
} from '../services/api';
import api from '../services/api';
import { useDatasetStore } from '../stores/datasetStore';

const { Title, Text } = Typography;
const { Dragger } = Upload;

const DEFAULT_ENTITY_TYPES = [
  'organization',
  'person',
  'location',
  'event',
  'concept',
  'technology',
];

const ACCEPTED_EXTENSIONS = '.txt,.md,.csv,.pdf,.docx';

type EntityMode = 'default' | 'manual' | 'auto';

interface IndexingState {
  active: boolean;
  datasetId: string | null;
  currentStep: number;
  progress: number;
  statusMessage: string;
  status: 'idle' | 'running' | 'completed' | 'failed';
  error: string | null;
}

const STEP_MAP: Record<string, number> = {
  starting: 0,
  init: 0,
  initializing: 0,
  config: 1,
  configuring: 1,
  'write settings': 1,
  'write prompts': 1,
  validate_api: 2,
  validating: 2,
  check_api: 2,
  'check api': 2,
  build: 3,
  building: 3,
  indexing: 3,
  community_detection: 3,
  'graphrag index': 3,
  done: 3,
  completed: 3,
};

function resolveStep(step: string): number {
  const lower = step.toLowerCase();
  if (STEP_MAP[lower] !== undefined) return STEP_MAP[lower];
  for (const [key, val] of Object.entries(STEP_MAP)) {
    if (lower.includes(key)) return val;
  }
  return 0;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Status pill: colored rounded tag for index state */
function IndexStatusPill({ indexComplete, hasIndex }: { indexComplete: boolean; hasIndex: boolean }) {
  if (indexComplete) {
    return (
      <Tag
        icon={<CheckCircleOutlined />}
        color="success"
        style={{ borderRadius: 10, padding: '0 10px', fontSize: 12 }}
      >
        已索引
      </Tag>
    );
  }
  if (hasIndex) {
    return (
      <Tag
        color="warning"
        style={{ borderRadius: 10, padding: '0 10px', fontSize: 12 }}
      >
        部分索引
      </Tag>
    );
  }
  return (
    <Tag
      color="default"
      style={{ borderRadius: 10, padding: '0 10px', fontSize: 12 }}
    >
      未索引
    </Tag>
  );
}

const DatasetManager: React.FC = () => {
  const { datasets, selectedId, loading, fetchDatasets, selectDataset } =
    useDatasetStore();

  // ── Form state ────────────────────────────────────────────────────
  const [formStep, setFormStep] = useState(0);
  const [name, setName] = useState('');
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [rawFiles, setRawFiles] = useState<(File & { uid: string })[]>([]);
  const [entityMode, setEntityMode] = useState<EntityMode>('default');
  const [manualTypes, setManualTypes] = useState<string[]>([]);
  const [autoTypes, setAutoTypes] = useState<string[]>([]);
  const [discovering, setDiscovering] = useState(false);

  // ── Indexing state ────────────────────────────────────────────────
  const [indexing, setIndexing] = useState<IndexingState>({
    active: false,
    datasetId: null,
    currentStep: 0,
    progress: 0,
    statusMessage: '',
    status: 'idle',
    error: null,
  });
  const [building, setBuilding] = useState(false);
  const pollingIntervalRef = useRef<number | null>(null);
  const statusRef = useRef<string | null>(null);

  // ── Fetch on mount ────────────────────────────────────────────────
  useEffect(() => {
    fetchDatasets();
  }, [fetchDatasets]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current !== null) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  }, []);

  // ── Step validation ───────────────────────────────────────────────
  const canGoNext = useCallback(
    (step: number) => {
      switch (step) {
        case 0:
          return name.trim().length > 0;
        case 1:
          return rawFiles.length > 0;
        case 2:
          return true; // entity config always valid (has defaults)
        default:
          return false;
      }
    },
    [name, rawFiles],
  );

  // ── File handling ─────────────────────────────────────────────────
  const handleBeforeUpload = useCallback(
    (file: File & { uid: string }) => {
      const exists = rawFiles.some(
        (f) => f.name === file.name && f.size === file.size,
      );
      if (exists) return false;
      setRawFiles((prev) => [...prev, file]);
      return false;
    },
    [rawFiles],
  );

  const handleFileRemove = useCallback((file: UploadFile) => {
    setRawFiles((prev) => prev.filter((f) => f.uid !== file.uid));
    setFileList((prev) => prev.filter((f) => f.uid !== file.uid));
    return true;
  }, []);

  const handleFileChange = useCallback(
    ({ fileList: newFileList }: { fileList: UploadFile[] }) => {
      setFileList(newFileList);
      const uids = new Set(newFileList.map((f) => f.uid));
      setRawFiles((prev) => prev.filter((f) => uids.has(f.uid)));
    },
    [],
  );

  // ── Discover entity types ─────────────────────────────────────────
  const handleDiscover = useCallback(async () => {
    if (rawFiles.length === 0) {
      message.warning('请先上传文件');
      return;
    }
    setDiscovering(true);
    try {
      const file = rawFiles[0];
      const text = await file.text();
      const sampleText = text.slice(0, 5000);
      if (sampleText.length < 10) {
        message.warning('文件内容过短，无法自动发现实体类型');
        return;
      }
      const result = await discoverEntityTypes(sampleText);
      setAutoTypes(result.entity_types);
      message.success(`发现 ${result.entity_types.length} 种实体类型`);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '自动发现实体类型失败');
    } finally {
      setDiscovering(false);
    }
  }, [rawFiles]);

  // ── Polling for status updates ────────────────────────────────────────
  const startPolling = useCallback(
    (datasetId: string) => {
      // Clear any existing polling
      if (pollingIntervalRef.current !== null) {
        clearInterval(pollingIntervalRef.current);
      }

      const poll = async () => {
        try {
          const response = await api.get(`/datasets/${datasetId}/index/status`);
          const data = response.data;

          // Ignore idle status — backend hasn't started indexing yet
          if (data.status === 'idle') return;

          const stepNum = resolveStep(data.step || '');
          const prevStatus = statusRef.current;

          // Update status ref before showing messages
          if (prevStatus !== data.status) {
            statusRef.current = data.status;
          }

          setIndexing((prev) => ({
            ...prev,
            currentStep: data.status === 'completed' ? 4 : stepNum,
            progress: data.progress ?? prev.progress,
            statusMessage: data.message || data.step || '',
            status: data.status,
            error: data.error || null,
          }));

          if (data.status === 'completed' && prevStatus !== 'completed') {
            if (pollingIntervalRef.current !== null) {
              clearInterval(pollingIntervalRef.current);
              pollingIntervalRef.current = null;
            }
            setBuilding(false);
            statusRef.current = null;
            message.success('知识图谱构建完成！');
            fetchDatasets();
          } else if (data.status === 'failed' && prevStatus !== 'failed') {
            if (pollingIntervalRef.current !== null) {
              clearInterval(pollingIntervalRef.current);
              pollingIntervalRef.current = null;
            }
            setBuilding(false);
            statusRef.current = null;
            const errorMsg = data.error || '知识图谱构建失败';
            message.error(`知识图谱构建失败: ${errorMsg}`);
          }
        } catch (err: any) {
          console.error('Failed to poll status:', err);
          // The polling will continue, so don't stop building
        }
      };

      // Reset status ref
      statusRef.current = null;

      // Poll every 2 seconds
      pollingIntervalRef.current = window.setInterval(poll, 2000);
      // Start first poll immediately
      poll();
    },
    [fetchDatasets],
  );

  // ── Build knowledge graph ─────────────────────────────────────────
  const handleBuild = useCallback(async () => {
    if (!name.trim() || rawFiles.length === 0) return;

    setBuilding(true);
    setIndexing({
      active: true,
      datasetId: null,
      currentStep: 0,
      progress: 0,
      statusMessage: '正在创建数据集...',
      status: 'running',
      error: null,
    });

    try {
      const dataset = await createDataset(name.trim());
      const datasetId = dataset.id;

      setIndexing((prev) => ({
        ...prev,
        datasetId,
        statusMessage: '正在上传文件...',
        progress: 10,
      }));

      await uploadDocuments(datasetId, rawFiles);

      // Give backend time to finalize file writes
      await new Promise(resolve => setTimeout(resolve, 500));

      setIndexing((prev) => ({
        ...prev,
        statusMessage: '正在启动索引...',
        progress: 25,
      }));

      let entityTypes: string[] | undefined;
      let mode: string = entityMode;
      if (entityMode === 'default') {
        entityTypes = undefined;
        mode = 'default';
      } else if (entityMode === 'manual') {
        entityTypes = manualTypes.length > 0 ? manualTypes : undefined;
        mode = 'manual';
      } else if (entityMode === 'auto') {
        entityTypes = autoTypes.length > 0 ? autoTypes : undefined;
        mode = 'auto';
      }

      // Wait a bit to ensure previous operations complete
      await new Promise(resolve => setTimeout(resolve, 300));

      // Connect SSE before starting indexing, so we don't miss any updates
      startPolling(datasetId);

      // Now start indexing - backend will update status and SSE will receive it
      await startIndexing(datasetId, entityTypes, mode);
    } catch (err: any) {
      setBuilding(false);
      setIndexing((prev) => ({
        ...prev,
        status: 'failed',
        error: err?.response?.data?.detail || err?.message || '构建过程中出错',
      }));
      message.error('构建知识图谱失败');
    }
  }, [name, rawFiles, entityMode, manualTypes, autoTypes, startPolling]);

  // ── Build existing dataset ────────────────────────────────────────
  const handleBuildExisting = useCallback(
    async (datasetId: string) => {
      setBuilding(true);
      setIndexing({
        active: true,
        datasetId,
        currentStep: 0,
        progress: 0,
        statusMessage: '正在启动索引...',
        status: 'running',
        error: null,
      });

      try {
        // Wait a bit to ensure everything is ready
        await new Promise(resolve => setTimeout(resolve, 300));

        // Connect SSE before starting indexing
        startPolling(datasetId);
        // Then start indexing
        await startIndexing(datasetId, undefined, 'default');
      } catch (err: any) {
        setBuilding(false);
        setIndexing((prev) => ({
          ...prev,
          status: 'failed',
          statusMessage: '启动索引失败',
          error: err?.response?.data?.detail || err.message || '未知错误',
        }));
      }
    },
    [startPolling],
  );

  // ── Delete dataset ────────────────────────────────────────────────
  const handleDelete = useCallback(
    async (id: string) => {
      try {
        await deleteDataset(id);
        if (selectedId === id) selectDataset(null);
        message.success('数据集已删除');
        fetchDatasets();
      } catch {
        message.error('删除失败');
      }
    },
    [fetchDatasets, selectDataset, selectedId],
  );

  // ── Reset form ────────────────────────────────────────────────────
  const resetForm = useCallback(() => {
    setFormStep(0);
    setName('');
    setFileList([]);
    setRawFiles([]);
    setEntityMode('default');
    setManualTypes([]);
    setAutoTypes([]);
  }, []);

  // ══════════════════════════════════════════════════════════════════
  //  Step content renderers
  // ══════════════════════════════════════════════════════════════════

  const renderStepName = () => (
    <div>
      <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
        为你的数据集起一个名称，用于标识和管理。
      </Text>
      <Input
        size="large"
        placeholder="输入数据集名称"
        value={name}
        onChange={(e) => setName(e.target.value)}
        maxLength={100}
        showCount
        autoFocus
        onPressEnter={() => canGoNext(0) && setFormStep(1)}
      />
    </div>
  );

  const renderStepUpload = () => (
    <div>
      <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
        上传文本文件，支持 .txt、.md、.csv、.pdf、.docx，可多选。
      </Text>
      <Dragger
        accept={ACCEPTED_EXTENSIONS}
        multiple
        fileList={fileList}
        beforeUpload={handleBeforeUpload as any}
        onRemove={handleFileRemove}
        onChange={handleFileChange}
      >
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">点击或拖拽文件到此区域</p>
        <p className="ant-upload-hint">
          支持 .txt, .md, .csv, .pdf, .docx
        </p>
      </Dragger>
      {rawFiles.length > 0 && (
        <div style={{ marginTop: 10, padding: '8px 12px', background: '#f6ffed', borderRadius: 6 }}>
          <Text style={{ fontSize: 13 }}>
            <CheckCircleOutlined style={{ color: '#52c41a', marginRight: 6 }} />
            已选择 <Text strong>{rawFiles.length}</Text> 个文件，共{' '}
            {formatFileSize(rawFiles.reduce((sum, f) => sum + f.size, 0))}
          </Text>
        </div>
      )}
    </div>
  );

  const renderStepConfig = () => (
    <div>
      <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
        配置实体抽取的类型，决定图谱中包含哪些类别的实体。
      </Text>
      <Tabs
        activeKey={entityMode}
        onChange={(key) => setEntityMode(key as EntityMode)}
        size="small"
        items={[
          {
            key: 'default',
            label: '默认类型',
            children: (
              <div style={{ padding: '4px 0' }}>
                <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
                  使用预设的通用实体类型：
                </Text>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                  {DEFAULT_ENTITY_TYPES.map((t) => (
                    <Tag key={t} color="blue">{t}</Tag>
                  ))}
                </div>
              </div>
            ),
          },
          {
            key: 'manual',
            label: '手动输入',
            children: (
              <div style={{ padding: '4px 0' }}>
                <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
                  输入自定义类型后按回车，如 person, organization
                </Text>
                <Select
                  mode="tags"
                  placeholder="输入后按回车添加"
                  value={manualTypes}
                  onChange={setManualTypes}
                  style={{ width: '100%' }}
                  tokenSeparators={[',', '，']}
                />
              </div>
            ),
          },
          {
            key: 'auto',
            label: '自动发现',
            children: (
              <div style={{ padding: '4px 0' }}>
                <Button
                  onClick={handleDiscover}
                  loading={discovering}
                  icon={<ExperimentOutlined />}
                  disabled={rawFiles.length === 0}
                  style={{ marginBottom: 8 }}
                >
                  从文件内容中识别
                </Button>
                {autoTypes.length > 0 && (
                  <Select
                    mode="tags"
                    value={autoTypes}
                    onChange={setAutoTypes}
                    style={{ width: '100%' }}
                    tokenSeparators={[',', '，']}
                  />
                )}
                {rawFiles.length === 0 && (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    请先在上一步上传文件
                  </Text>
                )}
              </div>
            ),
          },
        ]}
      />
    </div>
  );

  const renderStepConfirm = () => {
    const totalSize = rawFiles.reduce((sum, f) => sum + f.size, 0);
    const entityLabel =
      entityMode === 'default'
        ? `默认 (${DEFAULT_ENTITY_TYPES.length} 种)`
        : entityMode === 'manual'
          ? `自定义 (${manualTypes.length} 种)`
          : `自动发现 (${autoTypes.length} 种)`;

    return (
      <div>
        <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
          确认以下信息，然后点击「开始构建」。
        </Text>
        <div
          style={{
            background: '#fafafa',
            borderRadius: 8,
            padding: '16px 20px',
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <Text type="secondary">数据集名称</Text>
            <Text strong>{name}</Text>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <Text type="secondary">文件数量</Text>
            <Text strong>
              {rawFiles.length} 个 ({formatFileSize(totalSize)})
            </Text>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Text type="secondary">实体类型</Text>
            <Tag color="blue">{entityLabel}</Tag>
          </div>
        </div>
        <Button
          type="primary"
          size="large"
          block
          icon={<RocketOutlined />}
          disabled={building}
          loading={building}
          onClick={handleBuild}
          style={{ marginTop: 20 }}
        >
          开始构建知识图谱
        </Button>
      </div>
    );
  };

  // ══════════════════════════════════════════════════════════════════
  //  Indexing progress banner
  // ══════════════════════════════════════════════════════════════════

  const renderProgressBanner = () => {
    if (!indexing.active) return null;

    const isFailed = indexing.status === 'failed';
    const isDone = indexing.status === 'completed';

    return (
      <Card
        size="small"
        style={{
          marginTop: 16,
          borderColor: isFailed ? '#ff4d4f' : isDone ? '#52c41a' : '#1677ff',
          background: isFailed ? '#fff2f0' : isDone ? '#f6ffed' : '#e6f4ff',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          {isFailed ? (
            <CloseCircleFilled style={{ color: '#ff4d4f', fontSize: 16 }} />
          ) : isDone ? (
            <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 16 }} />
          ) : (
            <ThunderboltOutlined style={{ color: '#1677ff', fontSize: 16 }} />
          )}
          <Text strong>
            {isFailed ? '构建失败' : isDone ? '构建完成' : '正在构建知识图谱...'}
          </Text>
          <Text type="secondary" style={{ fontSize: 12, marginLeft: 'auto' }}>
            {indexing.statusMessage}
          </Text>
        </div>

        <Steps
          current={indexing.currentStep}
          status={isFailed ? 'error' : isDone ? 'finish' : 'process'}
          size="small"
          style={{ marginBottom: 12 }}
          items={[
            { title: '初始化' },
            { title: '配置' },
            { title: '验证 API' },
            { title: '构建图谱' },
          ]}
        />

        <Progress
          percent={indexing.progress}
          status={isFailed ? 'exception' : isDone ? 'success' : 'active'}
          size="small"
        />

        {indexing.error && (
          <Alert
            type="error"
            message={indexing.error}
            showIcon
            closable
            style={{ marginTop: 10 }}
          />
        )}
      </Card>
    );
  };

  // ══════════════════════════════════════════════════════════════════
  //  Dataset list
  // ══════════════════════════════════════════════════════════════════

  const renderDatasetList = () => {
    if (loading) {
      return (
        <div style={{ textAlign: 'center', padding: 48 }}>
          <Spin size="large" />
        </div>
      );
    }

    if (datasets.length === 0) {
      return (
        <div style={{ textAlign: 'center', padding: 48 }}>
          <DatabaseOutlined style={{ fontSize: 48, color: '#d9d9d9', marginBottom: 12 }} />
          <div>
            <Text type="secondary">暂无数据集，在左侧创建开始吧</Text>
          </div>
        </div>
      );
    }

    return (
      <List
        dataSource={[...datasets].sort(
          (a, b) => new Date(b.created).getTime() - new Date(a.created).getTime(),
        )}
        renderItem={(ds) => {
          const isSelected = selectedId === ds.id;
          const isIndexed = ds.index_complete;
          const hasPartial = ds.has_index && !ds.index_complete;

          return (
            <div
              onClick={() => selectDataset(ds.id)}
              style={{
                padding: '14px 16px',
                marginBottom: 8,
                borderRadius: 8,
                border: `1px solid ${isSelected ? '#1677ff' : '#f0f0f0'}`,
                background: isSelected ? '#e6f4ff' : '#fff',
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
            >
              {/* Row 1: Name + Status */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: 8,
                }}
              >
                <Space>
                  <Text strong style={{ fontSize: 14 }}>{ds.name}</Text>
                  <IndexStatusPill indexComplete={isIndexed} hasIndex={ds.has_index} />
                </Space>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  <ClockCircleOutlined style={{ marginRight: 4 }} />
                  {new Date(ds.created).toLocaleDateString('zh-CN')}
                </Text>
              </div>

              {/* Row 2: Stats + Actions */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <Space size={4}>
                  <Tag style={{ borderRadius: 4, fontSize: 12 }}>
                    实体 {ds.entity_count}
                  </Tag>
                  <Tag style={{ borderRadius: 4, fontSize: 12 }}>
                    关系 {ds.relationship_count}
                  </Tag>
                  <Tag style={{ borderRadius: 4, fontSize: 12 }}>
                    社区 {ds.community_count}
                  </Tag>
                </Space>

                <Space size={4} onClick={(e) => e.stopPropagation()}>
                  {!isIndexed && (
                    <Button
                      type={hasPartial ? 'default' : 'primary'}
                      size="small"
                      icon={<ThunderboltOutlined />}
                      disabled={building}
                      onClick={() => handleBuildExisting(ds.id)}
                    >
                      {hasPartial ? '重新构建' : '构建索引'}
                    </Button>
                  )}
                  <Popconfirm
                    title="确认删除？"
                    description="删除后无法恢复"
                    onConfirm={() => handleDelete(ds.id)}
                    okText="删除"
                    cancelText="取消"
                    okButtonProps={{ danger: true }}
                  >
                    <Button
                      type="text"
                      danger
                      size="small"
                      icon={<DeleteOutlined />}
                    />
                  </Popconfirm>
                </Space>
              </div>
            </div>
          );
        }}
      />
    );
  };

  // ══════════════════════════════════════════════════════════════════
  //  Main render
  // ══════════════════════════════════════════════════════════════════

  const STEP_ITEMS = [
    { title: '命名', icon: <FileTextOutlined /> },
    { title: '上传', icon: <InboxOutlined /> },
    { title: '配置', icon: <SettingOutlined /> },
    { title: '构建', icon: <RocketOutlined /> },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Title level={3} style={{ marginBottom: 24 }}>
        <DatabaseOutlined style={{ marginRight: 8 }} />
        数据集管理
      </Title>

      <Row gutter={24}>
        {/* ── Left: Step-guided form ── */}
        <Col xs={24} lg={10}>
          <Card
            title={
              <Space>
                <ThunderboltOutlined />
                <span>创建新数据集</span>
              </Space>
            }
          >
            {/* Steps indicator */}
            <Steps
              current={formStep}
              size="small"
              items={STEP_ITEMS}
              style={{ marginBottom: 28 }}
            />

            {/* Step content */}
            <div style={{ minHeight: 200 }}>
              {formStep === 0 && renderStepName()}
              {formStep === 1 && renderStepUpload()}
              {formStep === 2 && renderStepConfig()}
              {formStep === 3 && renderStepConfirm()}
            </div>

            {/* Navigation buttons (not shown on confirm step) */}
            {formStep < 3 && (
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  marginTop: 24,
                  paddingTop: 16,
                  borderTop: '1px solid #f0f0f0',
                }}
              >
                <Button
                  icon={<ArrowLeftOutlined />}
                  disabled={formStep === 0}
                  onClick={() => setFormStep((s) => s - 1)}
                >
                  上一步
                </Button>
                <Button
                  type="primary"
                  icon={<ArrowRightOutlined />}
                  disabled={!canGoNext(formStep)}
                  onClick={() => setFormStep((s) => s + 1)}
                >
                  下一步
                </Button>
              </div>
            )}

            {formStep === 3 && !building && (
              <div style={{ marginTop: 8 }}>
                <Button
                  type="link"
                  icon={<ArrowLeftOutlined />}
                  onClick={() => setFormStep(2)}
                  style={{ padding: 0 }}
                >
                  返回修改
                </Button>
              </div>
            )}
          </Card>

          {/* Progress banner — independent, visually prominent */}
          {renderProgressBanner()}
        </Col>

        {/* ── Right: Dataset list ── */}
        <Col xs={24} lg={14}>
          <Card
            title={
              <Space>
                <DatabaseOutlined />
                <span>已有数据集</span>
                <Tag>{datasets.length}</Tag>
              </Space>
            }
            extra={
              <Space>
                <Button
                  icon={<ReloadOutlined />}
                  size="small"
                  onClick={() => fetchDatasets()}
                  loading={loading}
                >
                  刷新
                </Button>
                {indexing.status === 'completed' && (
                  <Button size="small" onClick={resetForm}>
                    继续创建
                  </Button>
                )}
              </Space>
            }
          >
            {renderDatasetList()}
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default DatasetManager;
