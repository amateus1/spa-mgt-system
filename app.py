import streamlit as st
from streamlit_drawable_canvas import st_canvas
from aws_utils import AWSClient
import pandas as pd
from datetime import datetime

# --- SIMPLE PASSWORD AUTHENTICATION ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# If not authenticated, show login form
if not st.session_state.authenticated:
    st.title("水疗中心会员管理系统")
    login_placeholder = st.empty()
    with login_placeholder.form("login"):
        st.write("请输入密码访问系统")
        password = st.text_input("密码", type="password")
        submit_login = st.form_submit_button("登录")

        if submit_login:
            # Check against password stored in Streamlit secrets
            if password == st.secrets.get("APP_PASSWORD", "default_password"):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("密码不正确")
    # Stop execution if not authenticated
    st.stop()

# --- If authenticated, continue with the rest of the app ---

# 页面配置
st.set_page_config(
    page_title="水疗中心会员管理系统",
    page_icon="💆",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 初始化AWS客户端
@st.cache_resource
def init_aws_client():
    try:
        aws_access_key = st.secrets["AWS_ACCESS_KEY_ID"]
        aws_secret_key = st.secrets["AWS_SECRET_ACCESS_KEY"]
        region = st.secrets.get("AWS_REGION", "us-east-1")
        
        client = AWSClient(aws_access_key, aws_secret_key, region)
        return client
    except Exception as e:
        st.error(f"AWS客户端初始化错误: {e}")
        return None

# 初始化会话状态
if 'aws_client' not in st.session_state:
    st.session_state.aws_client = init_aws_client()

if 'current_member' not in st.session_state:
    st.session_state.current_member = None

if 'members_table' not in st.session_state:
    if st.session_state.aws_client:
        st.session_state.members_table = st.session_state.aws_client.create_members_table()
    else:
        st.session_state.members_table = None

if 'transactions_table' not in st.session_state:
    if st.session_state.aws_client:
        # Use new table structure
        st.session_state.transactions_table = st.session_state.aws_client.create_transactions_table('spa-transactions-v2')
    else:
        st.session_state.transactions_table = None

if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = False

if 'delete_confirmation' not in st.session_state:
    st.session_state.delete_confirmation = False

# 应用标题
st.title("💆 水疗中心会员管理系统")

# 侧边栏导航
st.sidebar.title("导航")
page = st.sidebar.radio("转到", ["控制面板", "会员管理", "管理交易", "查看历史记录"])

# 控制面板页面
if page == "控制面板":
    st.header("控制面板")
    
    # 快速统计
    if st.session_state.members_table:
        members = st.session_state.aws_client.search_members(st.session_state.members_table, "")
        st.metric("会员总数", len(members))
    
    # 搜索框
    st.subheader("查找会员")
    search_term = st.text_input("通过卡号或姓名搜索")
    
    if search_term:
        if st.session_state.members_table:
            members = st.session_state.aws_client.search_members(st.session_state.members_table, search_term)
            
            if members:
                st.write("搜索结果:")
                for member in members:
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        if st.button(f"选择", key=f"select_{member['card_id']}"):
                            st.session_state.current_member = member
                            st.rerun()
                    with col2:
                        st.write(f"**{member.get('name', '未知')}** (卡号: {member.get('card_id', 'N/A')}) - 余额: ￥{member.get('balance', 0):.2f}")
            else:
                st.info("未找到匹配的会员。")
        else:
            st.error("会员表未初始化")

# 会员管理页面
elif page == "会员管理":
    st.header("会员管理")
    
    # 添加新会员部分
    st.subheader("添加新会员")
    with st.form("add_member_form"):
        card_id = st.text_input("卡号 *")
        name = st.text_input("姓名 *")
        top_up_date = st.date_input("充值日期", value=datetime.now())
        initial_balance = st.number_input("初始余额 (￥)", min_value=0.0, step=50.0, value=0.0)
        
        submitted = st.form_submit_button("添加会员")
        
        if submitted:
            if not card_id or not name:
                st.error("卡号和姓名是必填字段")
            else:
                if st.session_state.members_table:
                    existing_member = st.session_state.aws_client.get_member(st.session_state.members_table, card_id)
                    if existing_member:
                        st.error("该卡号已存在，请使用不同的卡号。")
                    else:
                        success = st.session_state.aws_client.add_member(
                            st.session_state.members_table, 
                            card_id, 
                            name, 
                            top_up_date.isoformat(), 
                            initial_balance
                        )
                        
                        if success:
                            st.success(f"会员 {name} 添加成功!")
                            if st.session_state.transactions_table:
                                st.session_state.aws_client.add_transaction(
                                    st.session_state.transactions_table,
                                    card_id,
                                    initial_balance,
                                    service_notes="初始充值"
                                )
                        else:
                            st.error("添加会员失败。")
                else:
                    st.error("会员表未初始化")
    
    # 编辑和删除会员部分
    st.subheader("编辑或删除会员")
    
    edit_search_term = st.text_input("搜索要编辑的会员 (卡号或姓名)")
    
    if edit_search_term:
        if st.session_state.members_table:
            members = st.session_state.aws_client.search_members(st.session_state.members_table, edit_search_term)
            
            if members:
                member_options = {f"{m.get('name', '未知')} (卡号: {m.get('card_id', 'N/A')})": m for m in members}
                selected_member_label = st.selectbox("选择会员", list(member_options.keys()))
                selected_member = member_options[selected_member_label]
                
                st.write("**会员详情:**")
                st.write(f"卡号: {selected_member.get('card_id', 'N/A')}")
                st.write(f"姓名: {selected_member.get('name', '未知')}")
                st.write(f"充值日期: {selected_member.get('top_up_date', 'N/A')}")
                st.write(f"余额: ￥{selected_member.get('balance', 0):.2f}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("编辑此会员", key=f"edit_{selected_member['card_id']}"):
                        st.session_state.edit_mode = True
                        st.session_state.editing_member = selected_member
                with col2:
                    if st.button("删除此会员", key=f"delete_{selected_member['card_id']}"):
                        st.session_state.delete_confirmation = True
                        st.session_state.deleting_member = selected_member
                
                # 编辑模式
                if st.session_state.get('edit_mode', False) and st.session_state.get('editing_member', {}).get('card_id') == selected_member.get('card_id'):
                    with st.form("edit_member_form"):
                        new_name = st.text_input("姓名", value=selected_member.get('name', ''))
                        new_top_up_date = st.date_input("充值日期", value=datetime.fromisoformat(selected_member.get('top_up_date', datetime.now().isoformat())))
                        new_balance = st.number_input("余额", value=float(selected_member.get('balance', 0)))
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            saved = st.form_submit_button("保存更改")
                        with col2:
                            cancel = st.form_submit_button("取消")
                        
                        if saved:
                            success = st.session_state.aws_client.update_member(
                                st.session_state.members_table,
                                selected_member['card_id'],
                                new_name,
                                new_top_up_date.isoformat(),
                                new_balance
                            )
                            
                            if success:
                                st.success("会员信息更新成功!")
                                st.session_state.edit_mode = False
                                st.rerun()
                            else:
                                st.error("更新会员信息失败")
                        
                        if cancel:
                            st.session_state.edit_mode = False
                            st.rerun()
                
                # 删除确认
                if st.session_state.get('delete_confirmation', False) and st.session_state.get('deleting_member', {}).get('card_id') == selected_member.get('card_id'):
                    st.warning("⚠️ 确认删除该会员？此操作无法撤销！")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("确认删除", key="confirm_delete"):
                            success = st.session_state.aws_client.delete_member(
                                st.session_state.members_table,
                                selected_member['card_id']
                            )
                            
                            if success:
                                st.success("会员已删除")
                                st.session_state.delete_confirmation = False
                                
                                if st.session_state.transactions_table:
                                    transactions = st.session_state.aws_client.get_member_transactions(
                                        st.session_state.transactions_table,
                                        selected_member['card_id']
                                    )
                                    for transaction in transactions:
                                        st.session_state.aws_client.delete_transaction(
                                            st.session_state.transactions_table,
                                            transaction['transaction_id']
                                        )
                                st.rerun()
                            else:
                                st.error("删除会员失败")
                    
                    with col2:
                        if st.button("取消删除", key="cancel_delete"):
                            st.session_state.delete_confirmation = False
                            st.rerun()
            else:
                st.info("未找到匹配的会员。")
        else:
            st.error("会员表未初始化")

# 管理交易页面
elif page == "管理交易":
    st.header("管理交易")
    
    if st.session_state.current_member:
        member = st.session_state.current_member
        st.subheader(f"会员: {member.get('name', '未知')} (卡号: {member.get('card_id', 'N/A')})")
        st.write(f"当前余额: ￥{member.get('balance', 0):.2f}")
        
        # --- NEW: Transaction Type Selection ---
        transaction_type = st.radio("交易类型:", ["消费扣款", "余额充值"], horizontal=True)
        
        with st.form("transaction_form"):
            # Change label and min_value based on type
            if transaction_type == "消费扣款":
                amount = st.number_input("消费金额", min_value=0.01, step=50.0, value=50.0)
                amount = -abs(amount)  # Ensure amount is negative for charges
            else: # 余额充值
                amount = st.number_input("充值金额", min_value=0.01, step=100.0, value=100.0)
                amount = abs(amount)  # Ensure amount is positive for top-ups
                
            service_notes = st.text_input("备注（可选）")
            
            # Only require signature for charges, not top-ups
            if transaction_type == "消费扣款":
                st.write("客户签名:")
                # REPLACED: Using streamlit-drawable-canvas instead of streamlit-signature-canvas
                canvas_result = st_canvas(
                    fill_color="rgba(255, 165, 0, 0.3)",
                    stroke_width=2,
                    stroke_color="#000000",
                    background_color="#ffffff",
                    height=150,
                    width=400,
                    drawing_mode="freedraw",
                    key="signature_canvas",
                    display_toolbar=False
                )
                
                # Check if signature was drawn
                if canvas_result.image_data is not None:
                    signature = canvas_result
                else:
                    signature = None
            else:
                signature = None # No signature for top-ups
                
            submitted = st.form_submit_button("处理交易")
            
            if submitted:
                if amount == 0:
                    st.error("金额不能为零")
                else:
                    if st.session_state.members_table and st.session_state.transactions_table:
                        signature_key = None
                        # Only process signature if it's a charge and signature exists
                        if transaction_type == "消费扣款" and signature is not None and signature.image_data is not None:
                            # Convert numpy array to base64 for S3 upload
                            import base64
                            from io import BytesIO
                            from PIL import Image
                            
                            # Convert numpy array to PNG bytes, then to base64
                            img = Image.fromarray(signature.image_data.astype('uint8'), 'RGBA')
                            buffered = BytesIO()
                            img.save(buffered, format="PNG")
                            img_base64 = base64.b64encode(buffered.getvalue()).decode()
                            
                            signature_key = st.session_state.aws_client.upload_signature(
                                st.secrets["S3_BUCKET_NAME"],
                                img_base64,  # ← Now passing proper base64 string
                                member['card_id']
                            )
                            # Debug confirmation - ADDED HERE
                            if signature_key:
                                st.success(f"✓ 签名已保存到 S3: {signature_key}")
                            else:
                                st.error("✗ 签名保存失败")

                        #if transaction_type == "消费扣款" and signature is not None and signature.image_data is not None:
                        #    signature_key = st.session_state.aws_client.upload_signature(
                        #        st.secrets["S3_BUCKET_NAME"],
                        #        signature.image_data,
                        #        member['card_id']
                        #    )

                        
                        transaction_id = st.session_state.aws_client.add_transaction(
                            st.session_state.transactions_table,
                            member['card_id'],
                            amount, # This can now be positive or negative
                            signature_key,
                            service_notes
                        )
                        # ADD THIS DEBUG LINE
                        st.info(f"✅ 交易创建成功 - 交易ID: {transaction_id}")
                        
                        if transaction_id:
                            new_balance = st.session_state.aws_client.update_member_balance(
                                st.session_state.members_table,
                                member['card_id'],
                                amount # Add the amount (positive or negative)
                            )
                            
                            if new_balance is not None:
                                action = "扣款" if amount < 0 else "充值"
                                st.success(f"{action}成功! 新余额: ￥{new_balance:.2f}")
                                st.session_state.current_member['balance'] = new_balance
                                # st.rerun()
                            else:
                                st.error("更新会员余额失败")
                        else:
                            st.error("创建交易记录失败")
                    else:
                        st.error("数据库未初始化")
    else:
        st.info("请先从控制面板选择一个会员。")


# 查看历史记录页面
elif page == "查看历史记录":
    st.header("查看交易历史")
    
    if st.session_state.current_member:
        member = st.session_state.current_member
        st.subheader(f"会员: {member.get('name', '未知')} (卡号: {member.get('card_id', 'N/A')})")
        
        if st.session_state.transactions_table:
            transactions = st.session_state.aws_client.get_member_transactions(
                st.session_state.transactions_table,
                member['card_id']
            )
            # ADD DEBUG HERE (in app.py):
            st.write("🔍 DEBUG: 原始交易数据")
            st.write(f"检索到的交易数量: {len(transactions)}")
            for i, t in enumerate(transactions):
                st.write(f"交易 {i}: 时间 {t.get('timestamp')} - 金额 {t.get('amount')} - 项目 {t.get('service_notes', 'N/A')}")
            if transactions:
                df_data = []
                for t in transactions:
                    df_data.append({
                        '日期': t.get('timestamp', ''),
                        '金额': t.get('amount', 0),
                        '服务项目': t.get('service_notes', ''),
                        '签名': '有' if t.get('signature_s3_key') else '无'
                    })
                
                df = pd.DataFrame(df_data)
                if not df.empty:
                    df['日期'] = pd.to_datetime(df['日期']).dt.strftime('%Y-%m-%d %H:%M')
                st.dataframe(df)
                
                if not df.empty:
                    selected_index = st.selectbox("选择交易查看签名", range(len(df)), format_func=lambda x: f"交易 {x+1}")
                    
                    if df.iloc[selected_index]['签名'] == '有':
                        transaction = transactions[selected_index]
                        signature_key = transaction.get('signature_s3_key')
                        
                        if signature_key:
                            try:
                                s3_client = st.session_state.aws_client.s3
                                response = s3_client.get_object(
                                    Bucket=st.secrets["S3_BUCKET_NAME"],
                                    Key=signature_key
                                )
                                signature_img = response['Body'].read()
                                st.image(signature_img, caption="客户签名", width=300)
                            except Exception as e:
                                st.error(f"加载签名时出错: {e}")
            else:
                st.info("此会员暂无交易记录。")
        else:
            st.error("交易表未初始化")
    else:
        st.info("请先从控制面板选择一个会员。")

# 页脚
st.sidebar.markdown("---")
st.sidebar.info("水疗中心会员管理系统 v1.0")