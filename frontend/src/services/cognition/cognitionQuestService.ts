/**
 * Cognition Quest Service (Mock)
 * ECTA Quest - hybrid Oxigraph + Document DB architecture.
 * No actual DB or Oxigraph connection logic yet.
 */

import type { QuestPayload } from '../../types/cognition';

export class CognitionQuestService {
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
