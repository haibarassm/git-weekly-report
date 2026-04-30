"""公司管理 Tab - 增删改查公司信息"""
import gradio as gr
from integrations.company.company_service import CompanyService


def create_company_manage_tab():
    """创建公司管理 Tab"""
    service = CompanyService()

    with gr.Row():
        # 左列：公司列表
        with gr.Column(scale=1):
            gr.Markdown("### 公司列表")

            company_list = gr.Dataframe(
                headers=["ID", "名称", "行业", "职位"],
                datatype=["str", "str", "str", "str"],
                label="已配置的公司"
            )

            refresh_btn = gr.Button("🔄 刷新列表", size="sm")

            gr.Markdown("---")
            gr.Markdown("### 添加/编辑公司")

            company_id = gr.Textbox(
                label="公司ID",
                placeholder="如: zxfintec（英文，唯一标识）"
            )

            company_name = gr.Textbox(
                label="公司名称",
                placeholder="如: 杭州浙江甲骨文超级码科技股份有限公司"
            )

            company_industry = gr.Textbox(
                label="所属行业",
                placeholder="如: 移动互联网"
            )

            company_position = gr.Textbox(
                label="职位",
                placeholder="如: Java开发工程师"
            )

            add_btn = gr.Button("➕ 添加公司", variant="primary")
            update_btn = gr.Button("✏️ 更新公司", variant="secondary")
            delete_btn = gr.Button("🗑️ 删除公司", variant="stop")

            gr.Markdown("""
            **使用说明**
            1. 填写公司信息后点击"添加公司"
            2. 点击列表中的公司可自动填充到编辑框
            3. 修改后点击"更新公司"保存
            4. 点击"删除公司"可删除当前选中的公司

            **注意**: 删除公司后，关联的项目将变为无公司状态
            """)

        # 右列：状态显示
        with gr.Column(scale=2):
            gr.Markdown("### 操作状态")

            status = gr.Textbox(
                label="状态",
                lines=5,
                interactive=False
            )

            gr.Markdown("---")
            gr.Markdown("### 关联项目说明")

            gr.Markdown("""
            在项目管理页面中，每个项目可以关联一个公司。

            **工作经历生成规则**：
            - 有关联公司的项目 → 生成工作经历 + 项目经验
            - 无关联公司的项目 → 只生成项目经验（个人学习项目）

            **示例**：
            ```
            工作经历
            公司名称: 杭州浙江甲骨文超级码股份有限公司
            在职时间: 2020/04—至今
            主要职责: [从项目中提取]

            项目经验
            2020/04—至今    溯源产品线
            2024/01—至今    ChatPPT（个人项目）
            ```
            """)

    # 事件处理
    def _refresh_list():
        """刷新公司列表"""
        companies = service.get_companies()
        if not companies:
            return [], "暂无公司配置"

        data = []
        for c in companies:
            data.append([
                c.get("id", ""),
                c.get("name", ""),
                c.get("industry", ""),
                c.get("position", "")
            ])
        return data, f"✅ 已加载 {len(companies)} 家公司"

    def _add_company(id, name, industry, position):
        """添加公司"""
        if not id or not name:
            return "❌ 公司ID和名称不能为空", []

        company = {
            "id": id.strip(),
            "name": name.strip(),
            "industry": industry.strip() if industry else "",
            "position": position.strip() if position else ""
        }

        if service.add_company(company):
            data, _ = _refresh_list()
            return f"✅ 添加成功: {name}", data
        else:
            data, _ = _refresh_list()
            return f"❌ 添加失败: 公司ID '{id}' 已存在", data

    def _update_company(id, name, industry, position):
        """更新公司"""
        if not id or not name:
            data, _ = _refresh_list()
            return "❌ 公司ID和名称不能为空", data

        company = {
            "id": id.strip(),
            "name": name.strip(),
            "industry": industry.strip() if industry else "",
            "position": position.strip() if position else ""
        }

        if service.update_company(id.strip(), company):
            data, _ = _refresh_list()
            return f"✅ 更新成功: {name}", data
        else:
            data, _ = _refresh_list()
            return f"❌ 更新失败: 公司ID '{id}' 不存在", data

    def _delete_company(id):
        """删除公司"""
        if not id:
            data, _ = _refresh_list()
            return "❌ 请先选择要删除的公司", data

        if service.delete_company(id.strip()):
            data, _ = _refresh_list()
            return f"✅ 删除成功: {id}", data
        else:
            data, _ = _refresh_list()
            return f"❌ 删除失败: 公司ID '{id}' 不存在", data

    def _select_row(evt: gr.SelectData):
        """选择行时填充编辑框"""
        if evt is None:
            return None, None, None, None

        # 从选中行获取公司ID
        company_id = evt.row[0]
        company = service.get_company_by_id(company_id)

        if company:
            return (
                company.get("id", ""),
                company.get("name", ""),
                company.get("industry", ""),
                company.get("position", "")
            )
        return None, None, None, None

    # 绑定事件
    refresh_btn.click(
        fn=_refresh_list,
        outputs=[company_list, status]
    )

    add_btn.click(
        fn=_add_company,
        inputs=[company_id, company_name, company_industry, company_position],
        outputs=[status, company_list]
    )

    update_btn.click(
        fn=_update_company,
        inputs=[company_id, company_name, company_industry, company_position],
        outputs=[status, company_list]
    )

    delete_btn.click(
        fn=_delete_company,
        inputs=[company_id],
        outputs=[status, company_list]
    )

    company_list.select(
        fn=_select_row,
        outputs=[company_id, company_name, company_industry, company_position]
    )

    # 初始化时加载列表
    refresh_btn.click(
        fn=_refresh_list,
        outputs=[company_list, status]
    )

    return [company_list]
