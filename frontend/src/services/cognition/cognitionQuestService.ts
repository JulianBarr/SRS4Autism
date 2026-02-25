/**
 * Cognition Quest Service (Mock)
 * ECTA Quest - hybrid Oxigraph + Document DB architecture.
 * No actual DB or Oxigraph connection logic yet.
 */

import type { QuestPayload } from '../../types/cognition';

/** MacroObjective - high-level training goal within a module */
export interface MacroObjective {
  uri_id: string;
  label: string;
  phases?: QuestPayload[];
}

/** MacroObjectiveGroup - objectives grouped by recommended age bracket */
export interface MacroObjectiveGroup {
  ageBracket: string;
  objectives: MacroObjective[];
}

export class CognitionQuestService {
  /**
   * Get macro structure (Module -> MacroObjective by age bracket).
   * Returns hierarchical TOC for "认知发展篇" (Cognitive Development Module).
   * Data extracted from knowledge_graph/quest_full.ttl.
   */
  static async getMacroStructure(): Promise<MacroObjectiveGroup[]> {
    // TODO: SPARQL query Oxigraph for Module -> MacroObjective with recommendedAgeBracket
    // Hardcoded from knowledge_graph/quest_full.ttl - 认知发展篇, grouped by recommendedAgeBracket
    // Hardcoded obj_cog_044 phases - exact payload per user specification
    const phaseCount12 = {
      uri_id: 'ecta-inst:task_count_1_2',
      title: '数数(1-2)',
      materials: ['小物件', '积木', '鞋子'],
      environments: {
        structured_desktop: {
          steps: ['导师取2个积木并排摆开，指令"数一数"'],
          fading_prompts: ['全辅助', '部分辅助', '独立完成']
        },
        group_social: ['原地踏步时配合"1-2"指令', '音乐课拍手歌'],
        home_natural: ['洗手液挤两下', '每天数出2元硬币购物']
      }
    };
    const phaseMatchNum15 = {
      uri_id: 'ecta-inst:task_match_num_1_5',
      title: '数字配数字(1-5)',
      materials: ['数字卡片', '数字底板'],
      environments: {
        structured_desktop: {
          steps: ['出示数字卡片，指令"相同的数字放一起"'],
          fading_prompts: ['示范引导']
        },
        group_social: ['个人工作课数字配对', '按座位票数字找座位'],
        home_natural: ['看病拿号等待时凭单据数字排队']
      }
    };
    const phaseColorMatchIdentical: QuestPayload = {
      uri_id: 'ecta-inst:task_color_match_identical',
      title: '基础颜色配对 (相同颜色、形状)',
      materials: ['红色积木', '蓝色积木', '篮子'],
      environments: {
        structured_desktop: {
          steps: [
            '导师拿出颜色相同、形状相同的一组物件',
            '指令: 一样的颜色放一起'
          ],
          fading_prompts: {
            hard: ['全辅助: 拿着孩子的手放'],
            good: [],
            easy: ['独立完成']
          }
        },
        group_social: ['课前将相同颜色的成套座椅对应摆放'],
        home_natural: ['按颜色对头饰进行分类', '整理床品四件套']
      }
    };
    const phaseColorMatchDistractor: QuestPayload = {
      uri_id: 'ecta-inst:task_color_match_distractor',
      title: '抗干扰颜色配对 (增加干扰物)',
      materials: ['红色积木', '蓝色积木', '黄色雪花片'],
      environments: {
        structured_desktop: {
          steps: [
            '在桌面加入与目标颜色不同的干扰物',
            '指令: 把红色/蓝色的放一起'
          ],
          fading_prompts: {
            hard: ['全辅助: 指认干扰物并排除'],
            good: ['部分辅助: 口头提示'],
            easy: ['独立完成']
          }
        },
        group_social: ['小组活动中按颜色分组，有干扰物混入'],
        home_natural: ['整理玩具时排除不同颜色的物品', '按颜色叠放衣物']
      }
    };

    return [
      {
        ageBracket: '3-12个月',
        objectives: [
          { uri_id: 'ecta-inst:obj_cog_002', label: '学习控制自己的身体' },
          { uri_id: 'ecta-inst:obj_cog_003', label: '开始操控物件' },
          { uri_id: 'ecta-inst:obj_cog_005', label: '开始发展物件存在的概念' },
          { uri_id: 'ecta-inst:obj_cog_006', label: '尝试用声音以及动作表达' },
          { uri_id: 'ecta-inst:obj_cog_038', label: '发展进一步的分类概念' },
          { uri_id: 'ecta-inst:obj_cog_040', label: '理解事情或动作上的先后次序' },
          { uri_id: 'ecta-inst:obj_cog_041', label: '明白相对性的概念及词语' },
          {
            uri_id: 'ecta-inst:obj_cog_044',
            label: '明白简单的数量概念',
            phases: [phaseCount12, phaseMatchNum15]
          }
        ]
      },
      {
        ageBracket: '1-2岁',
        objectives: [
          { uri_id: 'ecta-inst:obj_cog_007a', label: '发展注视眼前事物的能力' },
          { uri_id: 'ecta-inst:obj_cog_007b', label: '发展视觉的追视能力' },
          { uri_id: 'ecta-inst:obj_cog_008', label: '发展视觉的辨别能力' },
          { uri_id: 'ecta-inst:obj_cog_011', label: '发展对声音的辨别能力' },
          { uri_id: 'ecta-inst:obj_cog_012', label: '发展对味道的辨别能力' },
          { uri_id: 'ecta-inst:obj_cog_013', label: '开始发展物件不变的概念' },
          { uri_id: 'ecta-inst:obj_cog_016', label: '认识与自己有关的事物' },
          { uri_id: 'ecta-inst:obj_cog_018', label: '学会常用物件的名称以及功用' },
          { uri_id: 'ecta-inst:obj_cog_020', label: '学会简单的类别概念' },
          { uri_id: 'ecta-inst:obj_cog_021', label: '学会简单因果关系' },
          { uri_id: 'ecta-inst:obj_cog_022', label: '学习物件在空间上的位置及先后次序' },
          { uri_id: 'ecta-inst:obj_cog_024', label: '会使用工具解决空间问题' }
        ]
      },
      {
        ageBracket: '2-3岁',
        objectives: [
          { uri_id: 'ecta-inst:obj_cog_025a', label: '发展对视觉刺激的专注力' },
          { uri_id: 'ecta-inst:obj_cog_025b', label: '发展对视觉刺激的辨别能力' },
          { uri_id: 'ecta-inst:obj_cog_028a', label: '发展对声音的辨别能力' },
          { uri_id: 'ecta-inst:obj_cog_028b', label: '辨别来自身体的感觉' },
          { uri_id: 'ecta-inst:obj_cog_029', label: '发展将物件符号化的能力' },
          {
            uri_id: 'ecta-inst:obj_cog_032',
            label: '认识物件的特性',
            phases: [phaseColorMatchIdentical, phaseColorMatchDistractor]
          },
          { uri_id: 'ecta-inst:obj_cog_036', label: '知道物件与物件之间的关系' }
        ]
      }
    ];
  }

  /**
   * Get quests that are unlocked given the set of completed quest URIs.
   * Static for convenient use from React components.
   *
   * 1. Query Oxigraph via SPARQL to find tasks where prerequisites are met.
   *    (All ecta-kg:requiresPrerequisite targets must be in completedUris)
   * 2. Fetch QuestPayload from DB for the resolved URIs.
   */
  static async getUnlockedQuests(completedUris: string[]): Promise<QuestPayload[]> {
    // TODO: SPARQL query Oxigraph for tasks where all prerequisites in completedUris
    // TODO: Fetch QuestPayload from DB for resolved URIs
    // Mock data based on ABA handbook - ECTA color matching tasks
    return [
      {
        uri_id: 'ecta-inst:task_color_match_identical',
        title: '基础颜色配对 (相同颜色、形状)',
        materials: ['红色积木', '蓝色积木', '篮子'],
        environments: {
          structured_desktop: {
            steps: [
              '导师拿出颜色相同、形状相同的一组物件',
              '指令: 一样的颜色放一起'
            ],
            fading_prompts: {
              hard: ['全辅助: 拿着孩子的手放'],
              good: [],
              easy: ['独立完成']
            }
          },
          group_social: ['课前将相同颜色的成套座椅对应摆放'],
          home_natural: ['按颜色对头饰进行分类', '整理床品四件套']
        }
      },
      {
        uri_id: 'ecta-inst:task_color_match_distractor',
        title: '抗干扰颜色配对 (增加干扰物)',
        materials: ['红色积木', '蓝色积木', '黄色雪花片'],
        environments: {
          structured_desktop: {
            steps: [
              '在桌面加入与目标颜色不同的干扰物',
              '指令: 把红色/蓝色的放一起'
            ],
            fading_prompts: {
              hard: ['全辅助: 指认干扰物并排除'],
              good: ['部分辅助: 口头提示'],
              easy: ['独立完成']
            }
          },
          group_social: ['小组活动中按颜色分组，有干扰物混入'],
          home_natural: ['整理玩具时排除不同颜色的物品', '按颜色叠放衣物']
        }
      }
    ];
  }

  /**
   * Get full quest details by URI.
   *
   * Fetch rich payload directly from DB.
   */
  static async getQuestDetails(uri: string): Promise<QuestPayload | null> {
    // TODO: Fetch rich payload directly from DB
    return null;
  }
}
