"""
管理员后台退出登录注入中间件
在 SimpleUI 用户下拉菜单的"注销"下方追加"退出登录"菜单项
"""


class AdminLogoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # 只处理 admin 页面的 HTML 响应
        if not request.path.startswith('/admin/'):
            return response
        # 跳过非 HTML、JS 翻译、登录页
        if request.path in ('/admin/jsi18n/', '/admin/login/'):
            return response

        content_type = response.get('Content-Type', '')
        if 'text/html' not in content_type:
            return response

        if not hasattr(response, 'content'):
            return response

        try:
            content = response.content.decode('utf-8')
        except (UnicodeDecodeError, AttributeError):
            return response

        if not request.user.is_authenticated:
            return response

        script = r'''
<script>
(function(){
    if(window.__logoutInjected)return;
    window.__logoutInjected=1;

    function insertLogoutItem(menu){
        if(!menu || menu.querySelector('.custom-logout-item'))return;
        var items=menu.querySelectorAll('.el-dropdown-menu__item');
        for(var i=0;i<items.length;i++){
            if(items[i].textContent.indexOf('注销')!==-1 || items[i].textContent.indexOf('Logout')!==-1){
                var li=document.createElement('li');
                li.className='el-dropdown-menu__item custom-logout-item';
                li.style.cssText='cursor:pointer;padding:0 20px;line-height:36px;color:#f56c6c;font-weight:600;font-size:13px;';
                li.textContent='退出登录';
                li.onclick=function(){
                    var f=document.getElementById('logout-form');
                    if(f){f.submit();}else{window.location.href='/admin/logout/';}
                };
                items[i].parentNode.insertBefore(li,items[i].nextSibling);
                return;
            }
        }
    }

    // 观察 DOM, 下拉菜单出现时插入
    var timer=null;
    var observer=new MutationObserver(function(mutations){
        for(var i=0;i<mutations.length;i++){
            for(var j=0;j<mutations[i].addedNodes.length;j++){
                var n=mutations[i].addedNodes[j];
                if(n.nodeType===1){
                    if(n.classList.contains('el-dropdown-menu')){
                        insertLogoutItem(n);
                    }else{
                        var m=n.querySelector('.el-dropdown-menu');
                        if(m)insertLogoutItem(m);
                    }
                }
            }
        }
    });
    observer.observe(document.body,{childList:true,subtree:true});
})();
</script>
'''

        content = content.replace('</body>', script + '</body>')
        response.content = content.encode('utf-8')
        return response
