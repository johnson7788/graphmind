import { useEffect, useRef, useState, useMemo } from 'react';
import {
  Layout,
  Select,
  Slider,
  Button,
  Drawer,
  Spin,
  Empty,
  Tag,
  Typography,
  Space,
  Descriptions,
  Divider,
  AutoComplete,
  Input,
  Image,
} from 'antd';
import {
  ReloadOutlined,
  NodeIndexOutlined,
  ApartmentOutlined,
  ClusterOutlined,
  InfoCircleOutlined,
  SearchOutlined,
  ArrowLeftOutlined,
  LinkOutlined,
} from '@ant-design/icons';
import Graph from 'graphology';
import Sigma from 'sigma';
import { NodeImageProgram } from '@sigma/node-image';
import forceAtlas2 from 'graphology-layout-forceatlas2';
import {
  getGraphData,
  getGraphStats,
  searchEntities,
  getEntityNeighborhood,
  graphImageUrl,
} from '../services/api';
import { useDatasetStore } from '../stores/datasetStore';

const { Sider, Content } = Layout;
const { Title, Text, Paragraph } = Typography;

// ---------------------------------------------------------------------------
// Types matching backend Pydantic schemas
// ---------------------------------------------------------------------------

interface GraphNode {
  id: string;
  label: string;
  type: string;
  description: string;
  color: string;
  size: number;
  image: string | null;
}

interface GraphEdge {
  from: string;
  to: string;
  label: string;
  weight: number;
}

interface GraphDataResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

interface GraphStatsResponse {
  entity_count: number;
  relationship_count: number;
  entity_types: Record<string, number>;
}

interface SelectedNodeInfo {
  id: string;
  label: string;
  type: string;
  description: string;
  color: string;
  image: string | null;
}

interface SelectedEdgeInfo {
  from: string;
  to: string;
  label: string;
  weight: number;
  fromNode?: GraphNode;
  toNode?: GraphNode;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function GraphView() {
  // Refs for sigma.js
  const containerRef = useRef<HTMLDivElement>(null);
  const sigmaRef = useRef<Sigma | null>(null);

  // Data state
  const [graphData, setGraphData] = useState<GraphDataResponse | null>(null);
  const [stats, setStats] = useState<GraphStatsResponse | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [graphLoading, setGraphLoading] = useState(false);

  // Filter state
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [nodeLimit, setNodeLimit] = useState(200);

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedNode, setSelectedNode] = useState<SelectedNodeInfo | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<SelectedEdgeInfo | null>(null);
  const [drawerType, setDrawerType] = useState<'node' | 'edge'>('node');

  // Entity search / exploration state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchOptions, setSearchOptions] = useState<Array<{ value: string; label: React.ReactNode }>>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [exploringEntity, setExploringEntity] = useState<string | null>(null);
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Zustand dataset store
  const { datasets, selectedId, selectDataset, fetchDatasets } = useDatasetStore();

  // ---------------------------------------------------------------------------
  // Initial dataset load
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (datasets.length === 0) {
      fetchDatasets();
    }
  }, [datasets.length, fetchDatasets]);

  // ---------------------------------------------------------------------------
  // Load stats when selected dataset changes
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!selectedId) {
      setStats(null);
      setSelectedTypes([]);
      return;
    }

    let cancelled = false;
    setStatsLoading(true);

    getGraphStats(selectedId)
      .then((data: GraphStatsResponse) => {
        if (!cancelled) {
          setStats(data);
          setSelectedTypes([]);
        }
      })
      .catch(() => {
        if (!cancelled) setStats(null);
      })
      .finally(() => {
        if (!cancelled) setStatsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  // ---------------------------------------------------------------------------
  // Load graph data when filters change (skip when exploring an entity)
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!selectedId || exploringEntity) {
      if (!selectedId) setGraphData(null);
      return;
    }

    let cancelled = false;
    setGraphLoading(true);

    getGraphData(
      selectedId,
      selectedTypes.length > 0 ? selectedTypes : undefined,
      nodeLimit,
    )
      .then((data: GraphDataResponse) => {
        if (!cancelled) setGraphData(data);
      })
      .catch(() => {
        if (!cancelled) setGraphData(null);
      })
      .finally(() => {
        if (!cancelled) setGraphLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedId, selectedTypes, nodeLimit, exploringEntity]);

  // ---------------------------------------------------------------------------
  // Entity search: debounced fuzzy search as user types
  // ---------------------------------------------------------------------------

  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);

    if (!value.trim() || !selectedId) {
      setSearchOptions([]);
      return;
    }

    setSearchLoading(true);
    searchTimerRef.current = setTimeout(() => {
      searchEntities(selectedId, value.trim())
        .then((results: Array<{ name: string; type: string }>) => {
          setSearchOptions(
            results.map((r) => ({
              value: r.name,
              label: (
                <Space>
                  <span>{r.name}</span>
                  <Tag color="blue" style={{ fontSize: 11 }}>{r.type}</Tag>
                </Space>
              ),
            })),
          );
        })
        .catch(() => setSearchOptions([]))
        .finally(() => setSearchLoading(false));
    }, 300);
  };

  const handleExploreEntity = (entityName: string) => {
    if (!selectedId || !entityName) return;
    setExploringEntity(entityName);
    setSearchQuery(entityName);
    setSearchOptions([]);
    setDrawerOpen(false);
  };

  const handleBackToFullGraph = () => {
    setExploringEntity(null);
    setSearchQuery('');
  };

  // ---------------------------------------------------------------------------
  // Load neighborhood subgraph when exploring an entity
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!exploringEntity || !selectedId) return;

    let cancelled = false;
    setGraphLoading(true);

    getEntityNeighborhood(selectedId, exploringEntity, 2)
      .then((data: GraphDataResponse) => {
        if (!cancelled) setGraphData(data);
      })
      .catch(() => {
        if (!cancelled) setGraphData(null);
      })
      .finally(() => {
        if (!cancelled) setGraphLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [exploringEntity, selectedId]);

  // ---------------------------------------------------------------------------
  // Initialize / update sigma.js whenever graphData changes
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!containerRef.current || !graphData) return;

    // Tear down previous instance
    sigmaRef.current?.kill();
    sigmaRef.current = null;

    if (graphData.nodes.length === 0) return;

    const graph = new Graph({ multi: true });

    graphData.nodes.forEach((n) => {
      const isRoot = exploringEntity != null && n.id === exploringEntity;
      // 任何解析到截图的多模态节点（image/table/chart/…）都渲染为图片缩略图，
      // 而不是普通圆形节点。
      const isImage = !!n.image;
      graph.addNode(n.id, {
        label: n.label,
        // Random initial placement; forceAtlas2 spreads them out.
        x: Math.random(),
        y: Math.random(),
        size: isRoot ? Math.min(n.size * 1.4, 60) : n.size,
        color: isRoot ? '#ff6b00' : n.color,
        type: isImage ? 'image' : 'circle',
        image: isImage && n.image ? graphImageUrl(selectedId!, n.image) : undefined,
      });
    });

    graphData.edges.forEach((e, idx) => {
      if (!graph.hasNode(e.from) || !graph.hasNode(e.to)) return;
      graph.addEdgeWithKey(`e-${idx}`, e.from, e.to, {
        size: Math.max(1, e.weight / 3),
        color: '#555566',
        type: 'arrow',
      });
    });

    // Force-directed layout for a readable spread.
    forceAtlas2.assign(graph, {
      iterations: graph.order > 400 ? 120 : 200,
      settings: {
        ...forceAtlas2.inferSettings(graph),
        gravity: 0.5,
        scalingRatio: 12,
        slowDown: 2,
      },
    });

    const sigma = new Sigma(graph, containerRef.current, {
      nodeProgramClasses: { image: NodeImageProgram },
      renderEdgeLabels: false,
      labelColor: { color: '#e0e0e0' },
      labelSize: 13,
      labelDensity: 0.4,
      labelGridCellSize: 80,
      defaultEdgeColor: '#555566',
      minCameraRatio: 0.1,
      maxCameraRatio: 10,
    });
    sigmaRef.current = sigma;

    // Hover highlighting: emphasize hovered node's neighborhood.
    let hoveredNode: string | null = null;
    sigma.setSetting('nodeReducer', (node, data) => {
      if (hoveredNode && node !== hoveredNode && !graph.areNeighbors(hoveredNode, node)) {
        return { ...data, color: '#2a2a3e', label: '' };
      }
      return data;
    });
    sigma.setSetting('edgeReducer', (edge, data) => {
      if (hoveredNode && !graph.extremities(edge).includes(hoveredNode)) {
        return { ...data, hidden: true };
      }
      return data;
    });

    sigma.on('enterNode', ({ node }) => {
      hoveredNode = node;
      sigma.refresh();
    });
    sigma.on('leaveNode', () => {
      hoveredNode = null;
      sigma.refresh();
    });

    // Single click → open detail drawer.
    sigma.on('clickNode', ({ node }) => {
      const n = graphData.nodes.find((x) => x.id === node);
      if (n) {
        setSelectedNode({
          id: n.id,
          label: n.label,
          type: n.type,
          description: n.description,
          color: n.color,
          image: n.image,
        });
        setSelectedEdge(null);
        setDrawerType('node');
        setDrawerOpen(true);
      }
    });

    // Double click → explore that node's neighborhood.
    sigma.on('doubleClickNode', ({ node, preventSigmaDefault }) => {
      preventSigmaDefault();
      handleExploreEntity(node);
    });

    sigma.on('clickEdge', ({ edge }) => {
      const idx = Number(edge.replace('e-', ''));
      const e = graphData.edges[idx];
      if (!e) return;
      const fromNode = graphData.nodes.find((n) => n.id === e.from);
      const toNode = graphData.nodes.find((n) => n.id === e.to);
      setSelectedEdge({
        from: e.from,
        to: e.to,
        label: e.label,
        weight: e.weight,
        fromNode,
        toNode,
      });
      setSelectedNode(null);
      setDrawerType('edge');
      setDrawerOpen(true);
    });

    return () => {
      sigmaRef.current?.kill();
      sigmaRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graphData, exploringEntity, selectedId]);

  // ---------------------------------------------------------------------------
  // Type filter options derived from stats
  // ---------------------------------------------------------------------------

  const typeOptions = useMemo(() => {
    if (!stats) return [];
    return Object.entries(stats.entity_types).map(([type, count]) => ({
      label: `${type} (${count})`,
      value: type,
    }));
  }, [stats]);

  // ---------------------------------------------------------------------------
  // Render: loading fallback
  // ---------------------------------------------------------------------------

  if (datasets.length === 0 && statsLoading) {
    return (
      <div style={{ textAlign: 'center', padding: 100 }}>
        <Spin size="large" tip="加载中..." />
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Main render
  // ---------------------------------------------------------------------------

  return (
    <div style={{ margin: -24, height: 'calc(100vh - 64px)' }}>
      <Layout style={{ height: '100%' }}>
        {/* ── Left sidebar: filters & stats ─────────────────────────── */}
        <Sider
          width={300}
          theme="light"
          style={{
            padding: '16px',
            overflowY: 'auto',
            borderRight: '1px solid #f0f0f0',
          }}
        >
          <Title level={4} style={{ marginBottom: 20 }}>
            <NodeIndexOutlined style={{ marginRight: 8 }} />
            图谱控制面板
          </Title>

          {/* Usage tip */}
          <div
            style={{
              marginBottom: 16,
              padding: '8px 12px',
              background: '#e6f4ff',
              borderRadius: 6,
              fontSize: 12,
              color: '#1677ff',
            }}
          >
            <InfoCircleOutlined style={{ marginRight: 4 }} />
            提示：单击查看详情，双击节点展开其邻域关系
          </div>

          {/* Dataset selector */}
          <div style={{ marginBottom: 20 }}>
            <Text strong style={{ display: 'block', marginBottom: 6 }}>
              数据集
            </Text>
            <Select
              style={{ width: '100%' }}
              placeholder="选择数据集"
              value={selectedId ?? undefined}
              onChange={(val) => selectDataset(val ?? null)}
              options={datasets.map((d) => ({
                label: `${d.name}${d.has_index ? '' : ' (未索引)'}`,
                value: d.id,
              }))}
              allowClear
              showSearch
              filterOption={(input, option) =>
                (option?.label as string)
                  ?.toLowerCase()
                  .includes(input.toLowerCase()) ?? false
              }
            />
          </div>

          {/* Empty state inside sidebar when no dataset selected */}
          {!selectedId && (
            <Empty
              description="请先选择数据集"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              style={{ marginTop: 60 }}
            />
          )}

          {selectedId && (
            <>
              {/* Type filter */}
              <div style={{ marginBottom: 20 }}>
                <Text strong style={{ display: 'block', marginBottom: 6 }}>
                  实体类型筛选
                </Text>
                <Select
                  mode="multiple"
                  style={{ width: '100%' }}
                  placeholder="全部类型"
                  value={selectedTypes}
                  onChange={setSelectedTypes}
                  options={typeOptions}
                  loading={statsLoading}
                  allowClear
                  maxTagCount="responsive"
                  disabled={!!exploringEntity}
                />
              </div>

              {/* Entity search / explore */}
              <div style={{ marginBottom: 20 }}>
                <Text strong style={{ display: 'block', marginBottom: 6 }}>
                  <SearchOutlined style={{ marginRight: 4 }} />
                  实体查找
                </Text>
                <AutoComplete
                  style={{ width: '100%' }}
                  options={searchOptions}
                  onSearch={handleSearchChange}
                  onSelect={handleExploreEntity}
                  value={searchQuery}
                  disabled={!selectedId}
                >
                  <Input
                    placeholder="输入实体名称模糊搜索..."
                    prefix={<SearchOutlined style={{ color: '#bfbfbf' }} />}
                    allowClear
                    suffix={searchLoading ? <Spin size="small" /> : undefined}
                  />
                </AutoComplete>
                {exploringEntity && (
                  <div style={{ marginTop: 8 }}>
                    <Tag
                      closable
                      color="orange"
                      onClose={handleBackToFullGraph}
                      style={{ fontSize: 13, padding: '4px 8px' }}
                    >
                      探索: {exploringEntity} (2层关系)
                    </Tag>
                    <Button
                      type="link"
                      size="small"
                      icon={<ArrowLeftOutlined />}
                      onClick={handleBackToFullGraph}
                      style={{ padding: 0, fontSize: 12 }}
                    >
                      返回全图
                    </Button>
                  </div>
                )}
              </div>

              {/* Node limit */}
              <div style={{ marginBottom: 20 }}>
                <Text strong style={{ display: 'block', marginBottom: 6 }}>
                  节点数量限制: {nodeLimit}
                </Text>
                <Slider
                  min={10}
                  max={500}
                  step={10}
                  value={nodeLimit}
                  onChange={setNodeLimit}
                  marks={{ 10: '10', 250: '250', 500: '500' }}
                  disabled={!!exploringEntity}
                />
              </div>

              {/* Refresh */}
              <Button
                icon={<ReloadOutlined />}
                onClick={() => {
                  if (exploringEntity) {
                    const entity = exploringEntity;
                    setExploringEntity(null);
                    setTimeout(() => setExploringEntity(entity), 50);
                  } else {
                    setSelectedTypes([...selectedTypes]);
                  }
                }}
                loading={graphLoading}
                block
                style={{ marginBottom: 20 }}
              >
                刷新图谱
              </Button>

              <Divider style={{ margin: '12px 0' }} />

              {/* Graph statistics */}
              {stats && (
                <div>
                  <Text strong style={{ display: 'block', marginBottom: 10 }}>
                    <InfoCircleOutlined style={{ marginRight: 4 }} />
                    图谱统计
                  </Text>
                  <Space direction="vertical" style={{ width: '100%' }} size={6}>
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        padding: '4px 8px',
                        background: '#fafafa',
                        borderRadius: 4,
                      }}
                    >
                      <Text>实体总数</Text>
                      <Text strong>{stats.entity_count}</Text>
                    </div>
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        padding: '4px 8px',
                        background: '#fafafa',
                        borderRadius: 4,
                      }}
                    >
                      <Text>关系总数</Text>
                      <Text strong>{stats.relationship_count}</Text>
                    </div>
                  </Space>

                  {/* Type distribution */}
                  {Object.keys(stats.entity_types).length > 0 && (
                    <div style={{ marginTop: 12 }}>
                      <Text strong style={{ display: 'block', marginBottom: 8 }}>
                        类型分布
                      </Text>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                        {Object.entries(stats.entity_types).map(([type, count]) => (
                          <Tag key={type} color="blue">
                            {type}: {count}
                          </Tag>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </Sider>

        {/* ── Graph canvas ──────────────────────────────────────────── */}
        <Content style={{ position: 'relative', overflow: 'hidden' }}>
          {!selectedId ? (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100%',
                background: '#1a1a2e',
              }}
            >
              <Empty
                description={
                  <Text style={{ color: '#888' }}>请选择数据集以查看知识图谱</Text>
                }
                image={<ApartmentOutlined style={{ fontSize: 80, color: '#444' }} />}
              />
            </div>
          ) : graphData && graphData.nodes.length === 0 && !graphLoading ? (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100%',
                background: '#1a1a2e',
              }}
            >
              <Empty
                description={
                  <Text style={{ color: '#888' }}>
                    暂无图谱数据，请先完成索引
                  </Text>
                }
                image={<ClusterOutlined style={{ fontSize: 80, color: '#444' }} />}
              />
            </div>
          ) : (
            <Spin spinning={graphLoading} tip="加载图谱数据..." size="large">
              <div
                ref={containerRef}
                style={{
                  width: '100%',
                  height: 'calc(100vh - 64px)',
                  background: '#1a1a2e',
                }}
              />
            </Spin>
          )}
        </Content>
      </Layout>

      {/* ── Node/Edge detail drawer ──────────────────────────────────────── */}
      <Drawer
        title={drawerType === 'node' ? '节点详情' : '关系详情'}
        open={drawerOpen}
        onClose={() => {
          setDrawerOpen(false);
          setSelectedNode(null);
          setSelectedEdge(null);
        }}
        width={420}
        destroyOnClose
      >
        {/* Edge detail */}
        {drawerType === 'edge' && selectedEdge && (
          <div>
            <div style={{ marginBottom: 16 }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  marginBottom: 12,
                  padding: '12px',
                  background: '#fff7e6',
                  borderRadius: 6,
                  border: '1px solid #ffd591',
                }}
              >
                <LinkOutlined style={{ fontSize: 20, color: '#fa8c16', marginRight: 12 }} />
                <div style={{ flex: 1 }}>
                  <Text strong style={{ fontSize: 14, display: 'block', marginBottom: 4 }}>
                    关系描述
                  </Text>
                  <Text style={{ fontSize: 13, color: '#595959' }}>
                    {selectedEdge.label || '暂无描述'}
                  </Text>
                </div>
              </div>

              <Descriptions column={1} bordered size="small">
                <Descriptions.Item label="关系强度">
                  <Tag color="orange" style={{ fontSize: 14, padding: '2px 10px' }}>
                    {selectedEdge.weight.toFixed(1)}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="起始实体">
                  {selectedEdge.fromNode ? (
                    <Space>
                      <Tag color={selectedEdge.fromNode.color} style={{ fontSize: 13 }}>
                        {selectedEdge.fromNode.type}
                      </Tag>
                      <Text strong>{selectedEdge.fromNode.label}</Text>
                    </Space>
                  ) : (
                    <Text>{selectedEdge.from}</Text>
                  )}
                </Descriptions.Item>
                <Descriptions.Item label="目标实体">
                  {selectedEdge.toNode ? (
                    <Space>
                      <Tag color={selectedEdge.toNode.color} style={{ fontSize: 13 }}>
                        {selectedEdge.toNode.type}
                      </Tag>
                      <Text strong>{selectedEdge.toNode.label}</Text>
                    </Space>
                  ) : (
                    <Text>{selectedEdge.to}</Text>
                  )}
                </Descriptions.Item>
              </Descriptions>
            </div>
          </div>
        )}

        {/* Node detail */}
        {drawerType === 'node' && selectedNode && (
          <div>
            {selectedNode.image && (
              <div style={{ marginBottom: 16, textAlign: 'center' }}>
                <Image
                  src={graphImageUrl(selectedId!, selectedNode.image)}
                  alt={selectedNode.label}
                  style={{ maxHeight: 240, borderRadius: 6 }}
                />
              </div>
            )}
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label="实体名称">
                <Text strong>{selectedNode.label}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="实体类型">
                <Tag
                  color={selectedNode.color}
                  style={{ fontSize: 14, padding: '2px 10px' }}
                >
                  {selectedNode.type}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="描述">
                <Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>
                  {selectedNode.description || '暂无描述'}
                </Paragraph>
              </Descriptions.Item>
            </Descriptions>
            <Button
              type="primary"
              icon={<NodeIndexOutlined />}
              block
              style={{ marginTop: 16 }}
              onClick={() => handleExploreEntity(selectedNode.id)}
            >
              展开此节点的关系
            </Button>
          </div>
        )}
      </Drawer>
    </div>
  );
}
