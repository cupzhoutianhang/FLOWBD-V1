"""
Part 5: Navigating the 5D Pareto Frontier

一个高级的 Pareto 优化导航系统，用于在 5 维评分空间中找到最优的权衡方案。

5 个维度：
1. 领域准确性 (Scientific Rigor)
2. 知识图谱利用度 (Regulatory Compliance / Graph Utilization)
3. 来源归属 (Ethical Soundness / Source Attribution)
4. 连贯性与一致性 (Recruitment Feasibility / Coherence)
5. 操作效率 (Operational Simplicity / Efficiency)

系统特点：
- 识别 Pareto 前沿
- 多维可视化
- 智能权衡策略
- 用户引导决策
"""

import os
import sys
import json
import logging
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime
import matplotlib.pyplot as plt
import pandas as pd
from scipy.spatial.distance import euclidean

# 此文件位于 src/agent/graphrag_and_rag/agent/ 目录
# 不需要重新配置 sys.path（已由 run_part5_enhanced.py 配置）

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Part 5.1: 数据结构
# ============================================================================

@dataclass
class DimensionScore:
    """单个维度的评分"""
    name: str                      # 维度名称
    score: float                   # 评分 (0.0-1.0)
    weight: float = 1.0           # 权重
    description: str = ""          # 描述
    
    def weighted_score(self) -> float:
        """加权评分"""
        return self.score * self.weight


@dataclass
class FiveDAchievements:
    """5维评分向量"""
    accuracy: DimensionScore           # 领域准确性
    graph_utilization: DimensionScore  # 知识图谱利用度
    source_attribution: DimensionScore # 来源归属
    coherence: DimensionScore          # 连贯性
    efficiency: DimensionScore         # 操作效率
    
    def to_vector(self) -> np.ndarray:
        """转换为 numpy 向量"""
        return np.array([
            self.accuracy.score,
            self.graph_utilization.score,
            self.source_attribution.score,
            self.coherence.score,
            self.efficiency.score
        ])
    
    def to_dict(self) -> Dict[str, float]:
        """转换为字典"""
        return {
            'accuracy': self.accuracy.score,
            'graph_utilization': self.graph_utilization.score,
            'source_attribution': self.source_attribution.score,
            'coherence': self.coherence.score,
            'efficiency': self.efficiency.score
        }
    
    def composite_score(self, weights: Optional[Dict[str, float]] = None) -> float:
        """计算加权综合评分"""
        if weights is None:
            weights = {
                'accuracy': 1.2,
                'graph_utilization': 1.0,
                'source_attribution': 0.9,
                'coherence': 1.1,
                'efficiency': 0.7
            }
        
        total = (
            self.accuracy.score * weights['accuracy'] +
            self.graph_utilization.score * weights['graph_utilization'] +
            self.source_attribution.score * weights['source_attribution'] +
            self.coherence.score * weights['coherence'] +
            self.efficiency.score * weights['efficiency']
        )
        
        total_weight = sum(weights.values())
        return total / total_weight if total_weight > 0 else 0.0


@dataclass
class SOPCandidate:
    """SOP 候选方案（在 Pareto 前沿上的一个点）"""
    version: str                   # 版本号
    sop_config: Dict[str, Any]     # SOP 配置
    evaluation: FiveDAchievements  # 5维评分
    generation_method: str = ""    # 生成方法
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    reasoning: str = ""            # 此方案的推理过程
    pipeline_state: Any = None     # 对应的AgentPipelineState对象（用于获取最终答案）
    
    def is_dominated_by(self, other: 'SOPCandidate') -> bool:
        """
        检查当前方案是否被其他方案支配
        
        支配定义：
        other 支配 self 当且仅当：
        - other 在所有维度上都 >= self
        - other 在至少一个维度上 > self
        """
        self_vec = self.evaluation.to_vector()
        other_vec = other.evaluation.to_vector()
        
        # 检查 other 是否在所有维度上都 >= self
        if not np.all(other_vec >= self_vec):
            return False
        
        # 检查 other 是否在至少一个维度上 > self
        if not np.any(other_vec > self_vec):
            return False
        
        return True
    
    def distance_to(self, other: 'SOPCandidate') -> float:
        """计算到另一个方案的欧几里得距离"""
        return euclidean(
            self.evaluation.to_vector(),
            other.evaluation.to_vector()
        )


# ============================================================================
# Part 5.2: Pareto 前沿分析
# ============================================================================

class ParetoFrontier:
    """
    Pareto 前沿分析器
    
    在 5 维评分空间中识别最优权衡点（非支配解）
    """
    
    def __init__(self):
        """初始化"""
        self.candidates: List[SOPCandidate] = []
        self.pareto_front: List[SOPCandidate] = []
        logger.info("✓ Pareto Frontier 分析器初始化")
    
    def add_candidate(self, candidate: SOPCandidate):
        """添加候选方案"""
        self.candidates.append(candidate)
    
    def identify_pareto_front(self) -> List[SOPCandidate]:
        """
        识别 Pareto 前沿（非支配解集）
        
        返回：
            所有非支配方案的列表
        """
        logger.info(f"🔍 分析 {len(self.candidates)} 个候选方案...")
        
        pareto_front = []
        
        for candidate in self.candidates:
            is_dominated = False
            
            for other in self.candidates:
                if candidate is other:
                    continue
                
                if candidate.is_dominated_by(other):
                    is_dominated = True
                    break
            
            if not is_dominated:
                pareto_front.append(candidate)
        
        self.pareto_front = sorted(
            pareto_front,
            key=lambda c: c.evaluation.composite_score(),
            reverse=True
        )
        
        logger.info(f"✓ 识别到 {len(self.pareto_front)} 个 Pareto 最优方案")
        
        return self.pareto_front
    
    def get_dominated_candidates(self) -> List[SOPCandidate]:
        """获取被支配的候选方案"""
        dominated = [c for c in self.candidates if c not in self.pareto_front]
        return dominated
    
    def print_frontier_summary(self):
        """打印 Pareto 前沿摘要"""
        if not self.pareto_front:
            logger.warning("Pareto 前沿为空")
            return
        
        logger.info("\n" + "=" * 80)
        logger.info("📊 Pareto 前沿分析结果")
        logger.info("=" * 80)
        logger.info(f"\n总候选方案数: {len(self.candidates)}")
        logger.info(f"Pareto 最优方案数: {len(self.pareto_front)}")
        logger.info(f"被支配方案数: {len(self.get_dominated_candidates())}")
        
        logger.info("\n【Pareto 前沿上的方案】\n")
        for i, candidate in enumerate(self.pareto_front, 1):
            scores = candidate.evaluation.to_dict()
            composite = candidate.evaluation.composite_score()
            
            logger.info(f"{i}. {candidate.version}")
            logger.info(f"   方法: {candidate.generation_method}")
            logger.info(f"   准确性:      {scores['accuracy']:.2f} ✓")
            logger.info(f"   图谱利用度:  {scores['graph_utilization']:.2f} ✓")
            logger.info(f"   来源归属:    {scores['source_attribution']:.2f} ✓")
            logger.info(f"   连贯性:      {scores['coherence']:.2f} ✓")
            logger.info(f"   操作效率:    {scores['efficiency']:.2f} ✓")
            logger.info(f"   综合评分:    {composite:.2f}")
            logger.info("")


# ============================================================================
# Part 5.3: 权衡分析和决策支持
# ============================================================================

class TradeoffAnalyzer:
    """
    权衡分析器
    
    帮助用户理解 Pareto 前沿上不同方案之间的权衡
    """
    
    def __init__(self, frontier: ParetoFrontier):
        """初始化"""
        self.frontier = frontier
        logger.info("✓ TradeoffAnalyzer 初始化")
    
    def identify_trade_dimensions(self, candidate1: SOPCandidate, candidate2: SOPCandidate) -> Dict[str, Dict[str, float]]:
        """
        识别两个方案之间的权衡维度
        
        返回哪些维度 candidate1 更好，哪些 candidate2 更好
        """
        scores1 = candidate1.evaluation.to_dict()
        scores2 = candidate2.evaluation.to_dict()
        
        trade_offs = {}
        for dim, score1 in scores1.items():
            score2 = scores2[dim]
            
            if score1 > score2:
                trade_offs[dim] = {
                    'winner': candidate1.version,
                    'diff': score1 - score2
                }
            elif score2 > score1:
                trade_offs[dim] = {
                    'winner': candidate2.version,
                    'diff': score2 - score1
                }
            else:
                trade_offs[dim] = {
                    'winner': 'tie',
                    'diff': 0.0
                }
        
        return trade_offs
    
    def recommend_based_on_preferences(self,
                                      priorities: Dict[str, float]) -> SOPCandidate:
        """
        根据用户偏好推荐最佳方案
        
        参数：
            priorities: 用户对各维度的优先级权重
                例如: {'accuracy': 2.0, 'efficiency': 1.0, ...}
        
        返回：
            最符合用户偏好的方案
        """
        if not self.frontier.pareto_front:
            raise ValueError("Pareto 前沿为空")
        
        best_candidate = None
        best_score = -1
        
        for candidate in self.frontier.pareto_front:
            scores = candidate.evaluation.to_dict()
            weighted_score = sum(
                scores[dim] * priorities.get(dim, 1.0)
                for dim in scores.keys()
            )
            
            if weighted_score > best_score:
                best_score = weighted_score
                best_candidate = candidate
        
        return best_candidate
    
    def print_trade_off_summary(self):
        """打印权衡摘要"""
        if len(self.frontier.pareto_front) < 2:
            logger.info("需要至少 2 个方案才能进行权衡分析")
            return
        
        logger.info("\n" + "=" * 80)
        logger.info("⚖️  权衡分析")
        logger.info("=" * 80)
        
        for i in range(len(self.frontier.pareto_front) - 1):
            cand1 = self.frontier.pareto_front[i]
            cand2 = self.frontier.pareto_front[i + 1]
            
            logger.info(f"\n【{cand1.version} vs {cand2.version}】")
            
            trades = self.identify_trade_dimensions(cand1, cand2)
            
            for dim, trade in trades.items():
                if trade['winner'] != 'tie':
                    logger.info(
                        f"  • {dim}: "
                        f"{trade['winner']} 更优 (+{trade['diff']:.3f})"
                    )


# ============================================================================
# Part 5.4: 可视化
# ============================================================================

class ParetoVisualizer:
    """
    Pareto 前沿可视化
    """
    
    @staticmethod
    def plot_2d_frontier(frontier: ParetoFrontier,
                         dim1: str = 'accuracy',
                         dim2: str = 'efficiency',
                         output_path: Optional[str] = None):
        """
        绘制 2D Pareto 前沿
        
        参数：
            frontier: Pareto 前沿
            dim1: 第一个维度
            dim2: 第二个维度
            output_path: 保存路径（可选）
        """
        if not frontier.pareto_front:
            logger.warning("Pareto 前沿为空，无法可视化")
            return
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Pareto 前沿上的点
        pareto_scores = [c.evaluation.to_dict() for c in frontier.pareto_front]
        pareto_x = [s[dim1] for s in pareto_scores]
        pareto_y = [s[dim2] for s in pareto_scores]
        
        # 被支配的点
        dominated = frontier.get_dominated_candidates()
        dominated_scores = [c.evaluation.to_dict() for c in dominated]
        dominated_x = [s[dim1] for s in dominated_scores]
        dominated_y = [s[dim2] for s in dominated_scores]
        
        # 绘制
        ax.scatter(pareto_x, pareto_y, c='red', s=200, marker='*',
                  label='Pareto Front', zorder=5)
        ax.scatter(dominated_x, dominated_y, c='gray', s=100, marker='o',
                  label='Dominated', alpha=0.5)
        
        # 添加标签
        for candidate in frontier.pareto_front:
            scores = candidate.evaluation.to_dict()
            ax.annotate(candidate.version,
                       (scores[dim1], scores[dim2]),
                       xytext=(5, 5), textcoords='offset points',
                       fontsize=10, fontweight='bold')
        
        ax.set_xlabel(f'{dim1.replace("_", " ").title()} Score', fontsize=12)
        ax.set_ylabel(f'{dim2.replace("_", " ").title()} Score', fontsize=12)
        ax.set_title(f'Pareto Frontier: {dim1} vs {dim2}', fontsize=14)
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, 1.05)
        ax.set_ylim(0, 1.05)
        
        if output_path:
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            logger.info(f"✓ 已保存到 {output_path}")
        
        plt.tight_layout()
        return fig, ax
    
    @staticmethod
    def plot_parallel_coordinates(frontier: ParetoFrontier,
                                  output_path: Optional[str] = None):
        """
        绘制平行坐标图（显示 5 维权衡）
        """
        if not frontier.pareto_front:
            logger.warning("Pareto 前沿为空，无法可视化")
            return
        
        # 准备数据
        data = []
        for candidate in frontier.pareto_front:
            scores = candidate.evaluation.to_dict()
            scores['version'] = candidate.version
            data.append(scores)
        
        df = pd.DataFrame(data)
        
        # 绘制
        fig, ax = plt.subplots(figsize=(12, 6))
        
        dimensions = ['accuracy', 'graph_utilization', 'source_attribution',
                     'coherence', 'efficiency']
        
        for idx, row in df.iterrows():
            version = row['version']
            values = [row[dim] for dim in dimensions]
            ax.plot(range(len(dimensions)), values, marker='o', 
                   label=version, linewidth=2, markersize=8)
        
        ax.set_xticks(range(len(dimensions)))
        ax.set_xticklabels([d.replace('_', '\n') for d in dimensions],
                           fontsize=10)
        ax.set_ylabel('Score', fontsize=12)
        ax.set_title('5D Performance Comparison (Parallel Coordinates)', fontsize=14)
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0, 1.05)
        
        if output_path:
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            logger.info(f"✓ 已保存到 {output_path}")
        
        plt.tight_layout()
        return fig, ax
    
    @staticmethod
    def plot_radar_chart(frontier: ParetoFrontier,
                        output_path: Optional[str] = None):
        """
        绘制雷达图（每个方案一个雷达）
        """
        if not frontier.pareto_front:
            logger.warning("Pareto 前沿为空，无法可视化")
            return
        
        dimensions = ['accuracy', 'graph_utilization', 'source_attribution',
                     'coherence', 'efficiency']
        n_dims = len(dimensions)
        
        # 角度
        angles = np.linspace(0, 2 * np.pi, n_dims, endpoint=False).tolist()
        angles += angles[:1]
        
        fig, axes = plt.subplots(
            1, len(frontier.pareto_front),
            figsize=(5 * len(frontier.pareto_front), 5),
            subplot_kw=dict(projection='polar')
        )
        
        if len(frontier.pareto_front) == 1:
            axes = [axes]
        
        for ax, candidate in zip(axes, frontier.pareto_front):
            scores = candidate.evaluation.to_dict()
            values = [scores[dim] for dim in dimensions]
            values += values[:1]
            
            ax.plot(angles, values, 'o-', linewidth=2, color='red')
            ax.fill(angles, values, alpha=0.25, color='red')
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(
                [d.replace('_', '\n') for d in dimensions],
                fontsize=10
            )
            ax.set_ylim(0, 1)
            ax.set_title(f'{candidate.version}', fontsize=12, fontweight='bold')
            ax.grid(True)
        
        fig.suptitle('5D Performance Radar Charts', fontsize=14, fontweight='bold')
        
        if output_path:
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            logger.info(f"✓ 已保存到 {output_path}")
        
        plt.tight_layout()
        return fig, axes


# ============================================================================
# Part 5.5: 决策引导系统
# ============================================================================

class ParetoDecisionGuide:
    """
    交互式决策引导系统
    
    帮助用户在 Pareto 前沿上做出最佳选择
    """
    
    def __init__(self, frontier: ParetoFrontier, analyzer: TradeoffAnalyzer):
        """初始化"""
        self.frontier = frontier
        self.analyzer = analyzer
        logger.info("✓ Pareto Decision Guide 初始化")
    
    def interactive_selection(self) -> SOPCandidate:
        """交互式选择最佳方案"""
        while True:
            print("\n" + "=" * 80)
            print("【Pareto 前沿决策指南】")
            print("=" * 80)
            
            print("\n可选方案：")
            for i, candidate in enumerate(self.frontier.pareto_front, 1):
                scores = candidate.evaluation.to_dict()
                composite = candidate.evaluation.composite_score()
                print(f"{i}. {candidate.version}")
                print(f"   准确性: {scores['accuracy']:.2f}, "
                      f"图谱: {scores['graph_utilization']:.2f}, "
                      f"来源: {scores['source_attribution']:.2f}, "
                      f"连贯: {scores['coherence']:.2f}, "
                      f"效率: {scores['efficiency']:.2f}")
                print(f"   综合评分: {composite:.2f}")
            
            print("\n选项：")
            print("  1. 按编号选择方案")
            print("  2. 按优先级推荐")
            print("  3. 查看权衡分析")
            print("  4. 返回")
            
            choice = input("\n请选择 (1-4): ").strip()
            
            if choice == '1':
                try:
                    idx = int(input("请输入方案编号: ")) - 1
                    if 0 <= idx < len(self.frontier.pareto_front):
                        return self.frontier.pareto_front[idx]
                    else:
                        print("❌ 无效的编号")
                except ValueError:
                    print("❌ 请输入有效的数字")
            
            elif choice == '2':
                print("\n请评估各维度的重要性 (1-5 分):")
                priorities = {}
                for dim in ['accuracy', 'graph_utilization', 'source_attribution',
                           'coherence', 'efficiency']:
                    while True:
                        try:
                            score = int(input(f"  {dim}: "))
                            if 1 <= score <= 5:
                                priorities[dim] = score
                                break
                        except ValueError:
                            pass
                        print("❌ 请输入 1-5 之间的数字")
                
                recommended = self.analyzer.recommend_based_on_preferences(priorities)
                print(f"\n✓ 推荐方案: {recommended.version}")
                
                if input("是否选择此方案? (y/n): ").lower() == 'y':
                    return recommended
            
            elif choice == '3':
                self.analyzer.print_trade_off_summary()
            
            elif choice == '4':
                return None
    
    def print_decision_summary(self, selected: SOPCandidate):
        """打印决策摘要"""
        print("\n" + "=" * 80)
        print("【决策摘要】")
        print("=" * 80)
        print(f"\n选择的方案: {selected.version}")
        print(f"生成方法: {selected.generation_method}")
        print(f"时间戳: {selected.timestamp}")
        
        scores = selected.evaluation.to_dict()
        print("\n5维评分：")
        print(f"  • 领域准确性:      {scores['accuracy']:.3f}")
        print(f"  • 知识图谱利用度:  {scores['graph_utilization']:.3f}")
        print(f"  • 来源归属:        {scores['source_attribution']:.3f}")
        print(f"  • 连贯性与一致性:  {scores['coherence']:.3f}")
        print(f"  • 操作效率:        {scores['efficiency']:.3f}")
        
        composite = selected.evaluation.composite_score()
        print(f"\n综合评分: {composite:.3f}/1.0")
        
        if selected.reasoning:
            print(f"\n推理过程：\n{selected.reasoning}")


# ============================================================================
# Part 5.6: 主系统
# ============================================================================

class ParetoFrontierNavigator:
    """
    5D Pareto 前沿导航系统
    
    整合所有模块，提供完整的多目标优化决策支持
    """
    
    def __init__(self):
        """初始化"""
        self.frontier = ParetoFrontier()
        self.analyzer = TradeoffAnalyzer(self.frontier)
        self.visualizer = ParetoVisualizer()
        self.guide = ParetoDecisionGuide(self.frontier, self.analyzer)
        logger.info("✓ ParetoFrontierNavigator 初始化完成")
    
    def add_sop_candidate(self, candidate: SOPCandidate):
        """添加 SOP 候选方案"""
        self.frontier.add_candidate(candidate)
    
    def analyze_frontier(self) -> List[SOPCandidate]:
        """分析并识别 Pareto 前沿"""
        return self.frontier.identify_pareto_front()
    
    def print_analysis(self):
        """打印完整分析结果"""
        self.frontier.print_frontier_summary()
        self.analyzer.print_trade_off_summary()
    
    def visualize(self, output_dir: Optional[str] = None):
        """生成所有可视化"""
        if output_dir is None:
            output_dir = "./pareto_visualizations"
        
        os.makedirs(output_dir, exist_ok=True)
        
        logger.info(f"\n📊 生成可视化图表到 {output_dir}...")
        
        # 2D 图表
        self.visualizer.plot_2d_frontier(
            self.frontier,
            dim1='accuracy',
            dim2='efficiency',
            output_path=os.path.join(output_dir, 'pareto_2d.png')
        )
        
        # 平行坐标图
        self.visualizer.plot_parallel_coordinates(
            self.frontier,
            output_path=os.path.join(output_dir, 'parallel_coordinates.png')
        )
        
        # 雷达图
        self.visualizer.plot_radar_chart(
            self.frontier,
            output_path=os.path.join(output_dir, 'radar_charts.png')
        )
        
        logger.info("✓ 所有可视化已生成")
    
    def interactive_decision(self) -> SOPCandidate:
        """交互式决策流程"""
        return self.guide.interactive_selection()
    
    def get_pareto_front(self) -> List[SOPCandidate]:
        """获取 Pareto 前沿"""
        return self.frontier.pareto_front
    
    def export_to_json(self, filepath: str):
        """将分析结果导出为 JSON"""
        result = {
            'total_candidates': len(self.frontier.candidates),
            'pareto_front_size': len(self.frontier.pareto_front),
            'pareto_candidates': [
                {
                    'version': c.version,
                    'scores': c.evaluation.to_dict(),
                    'composite_score': c.evaluation.composite_score(),
                    'generation_method': c.generation_method
                }
                for c in self.frontier.pareto_front
            ]
        }
        
        with open(filepath, 'w') as f:
            json.dump(result, f, indent=2)
        
        logger.info(f"✓ 分析结果已导出到 {filepath}")


if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("Part 5: Navigating the 5D Pareto Frontier")
    logger.info("=" * 80)
    
    print("\n✓ Part 5 Pareto 前沿导航系统已加载")
    print("  - ParetoFrontier: Pareto 前沿分析")
    print("  - TradeoffAnalyzer: 权衡分析")
    print("  - ParetoVisualizer: 多维可视化")
    print("  - ParetoDecisionGuide: 交互式决策")
    print("  - ParetoFrontierNavigator: 主系统")
