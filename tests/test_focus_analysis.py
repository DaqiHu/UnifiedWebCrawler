from __future__ import annotations

import unittest

import pandas as pd

from crawler_app.analysis import (
    build_cross_domain_candidates,
    build_low_prep_candidates,
    build_pipeline_edge_summary,
    build_pipeline_visibility_candidates,
    enrich_jobs_dataframe,
)


class FocusAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.jobs_df = enrich_jobs_dataframe(
            pd.DataFrame(
                [
                    {
                        "job_id": "8123",
                        "title": "游戏引擎开发实习生",
                        "category": "程序&技术类",
                        "summary": "",
                        "description": (
                            "1. 引擎模块开发与维护：参与游戏引擎核心子系统（如动画系统、物理模拟、资源管线、工具链等）的开发、功能拓展与性能优化\n"
                            "2. 跨平台与性能工程：协助解决引擎在Windows、Android、iOS等多平台的适配性、稳定性及性能问题\n"
                            "3. 技术方案研究与落地：在导师指导下，了解业界先进的引擎架构与解决方案，并在项目中评估与应用"
                        ),
                        "requirements": (
                            "1. 扎实的计算机基础、良好的数学功底和C++编程能力\n"
                            "2. 在渲染、动画、物理、资源复杂系统、工具链任意一个方向有深入了解\n"
                            "3. 至少熟悉一个OS系统（Windows/iOS/Android/PlayStation）"
                        ),
                        "bonus_points": "1. 有Unity/UE或自研引擎源码开发经验优先\n2. 有AIGC、AI 自动化、AI Agent 等相关应用经验者优先",
                        "delivery_instructions": "",
                        "tags_json": [],
                        "updated_at": "2026-03-09T00:00:00+00:00",
                    },
                    {
                        "job_id": "7883",
                        "title": "交互策划（UE）实习生",
                        "category": "产品策划类",
                        "summary": "加入游戏项目团队，学习游戏界面从设计到落地的完整流程。",
                        "description": (
                            "1. 负责游戏交互设计，完成需求分析、体验流程梳理，产出原型和说明文档；\n"
                            "2. 提供界面视觉表现、操作体验与反馈等方面的创意方案；\n"
                            "3. 跨多岗位协作，跟进开发进度，及时验收并推进迭代，确保方案高质量落地。"
                        ),
                        "requirements": (
                            "1. 熟悉体验设计、交互设计、视觉设计流程；\n"
                            "2. 熟练掌握Figma、PS、AI等设计工具，有Unity/UE引擎使用经验；\n"
                            "3. 热爱游戏，对玩家心理和游戏设计有一定理解。"
                        ),
                        "bonus_points": "",
                        "delivery_instructions": "【必需项】请务必提供个人游戏经历及相关作品。作品集尽量以PDF等文件格式提交。",
                        "tags_json": [],
                        "updated_at": "2026-03-09T00:00:00+00:00",
                    },
                    {
                        "job_id": "7901",
                        "title": "机械原画实习生",
                        "category": "美术&表现类",
                        "summary": "",
                        "description": (
                            "1. 设计枪械/载具/机械装置外观；\n"
                            "2. 与策划、动画、特效等团队成员紧密合作；\n"
                            "3. 研究现实世界中的机械结构和材质，并将其特点融入到游戏设计中。"
                        ),
                        "requirements": "1. 具备扎实的美术功底；\n2. 对工业机械结构和材质有浓厚兴趣；\n3. 具备优秀的沟通能力和团队合作精神。",
                        "bonus_points": "1. 掌握3Ds Max/Maya等设计软件，有模型制作、贴图绘制的能力；",
                        "delivery_instructions": "【作品集（必需项）】请选取能体现你专业美术能力的作品，整理为 PDF 或 PNG 等格式。",
                        "tags_json": ["写实", "硬表面", "机械", "载具"],
                        "updated_at": "2026-03-09T00:00:00+00:00",
                    },
                    {
                        "job_id": "9000",
                        "title": "AI产品实习生",
                        "category": "产品策划类",
                        "summary": "参与AI产品的需求梳理与功能设计。",
                        "description": "1. 协助产品经理进行需求分析；\n2. 跟进功能落地。",
                        "requirements": "1. 逻辑清晰，沟通良好；\n2. 对AI产品有兴趣。",
                        "bonus_points": "",
                        "delivery_instructions": "",
                        "tags_json": [],
                        "updated_at": "2026-03-09T00:00:00+00:00",
                    },
                ]
            )
        )

    def test_cross_domain_candidates_include_engine_and_ue_planning_roles(self) -> None:
        dataframe = build_cross_domain_candidates(self.jobs_df, limit=10)

        titles = dataframe["title"].tolist()

        self.assertIn("游戏引擎开发实习生", titles)
        self.assertIn("交互策划（UE）实习生", titles)

    def test_low_prep_candidates_rank_jobs_without_extra_materials_ahead_of_portfolio_roles(self) -> None:
        dataframe = build_low_prep_candidates(self.jobs_df, limit=10)

        ai_product_score = int(dataframe.loc[dataframe["title"] == "AI产品实习生", "prep_burden_score"].iloc[0])
        art_score = int(dataframe.loc[dataframe["title"] == "机械原画实习生", "prep_burden_score"].iloc[0])

        self.assertLess(ai_product_score, art_score)

    def test_pipeline_visibility_candidates_and_edges_capture_bridge_roles(self) -> None:
        dataframe = build_pipeline_visibility_candidates(self.jobs_df, limit=10)
        edges_df = build_pipeline_edge_summary(self.jobs_df, limit=10)

        titles = dataframe["title"].tolist()
        edges = edges_df["edge"].tolist()

        self.assertIn("交互策划（UE）实习生", titles)
        self.assertIn("游戏引擎开发实习生", titles)
        self.assertIn("策划/需求 <-> 技术/工程", edges)


if __name__ == "__main__":
    unittest.main()
