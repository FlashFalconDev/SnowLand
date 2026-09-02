window.nav = [
    {
        name : '主面板',
        href : '/panel/dashboard',
        icon : 'ri-dashboard-3-line',
        num  : 99
    },
    {
        name: '用戶',
        href: 'javascript:;',
        icon: 'ri-user-line',
        children: [
            {
                name: '會員資訊',
                href: '/Member/member_list'
            },
        ]
    },
    {
        name: '餐點',
        href: 'javascript:;',
        icon: 'ri-restaurant-2-line',
        children: [
            {
                name: '餐點分類',
                href: '/Item/item_food_category'
            },
            {
                name: '餐點資訊',
                href: '/ItemFood/item_food_info',
            },
            {
                name: '餐點訂單',
                href: '/Item/item_order_list'
            },
            {
                name: '標籤',
                href: 'https://ffsystem.ngrok.io/pp/dashboard/flashfalcon/'
            }
        ]
    },

    
    {
        name : '界面',
        href : 'javascript:;',
        icon : 'ri-layout-2-line',
        children: [
            {
                name: '布局',
                href: '/screen/layout.html?id=1'
            },
            {
                name: '颜色',
                href: '/screen/color'
            },
            {
                name: '间距',
                href: '/screen/space'
            },
            {
                name: '分割线',
                href: '/screen/divider'
            }
        ]
    },
    {
        name : '表单',
        href : 'javascript:;',
        icon : 'ri-edit-box-line',
        // 下级菜单
        children: [
            {
                name : '按钮',
                href : '/form/button'
            },
            {
                name : '输入框',
                href : '/form/input'
            },
            {
                name : '文本域',
                href : '/form/textarea'
            },
            {
                name : '单选',
                href : '/form/radio'
            },
            {
                name : '复选',
                href : '/form/checkbox'
            },
            {
                name : '下拉菜单',
                href : '/form/select'
            },
            {
                name : '上传',
                href : '/form/upload'
            },
            {
                name : '裁剪',
                href : '/form/cropping'
            }
        ]
    },
    {
        name : '增强',
        href : 'javascript:;',
        icon : 'ri-pen-nib-line',
        children: [
            {
                name : '穿梭框',
                href : '/enhance/transfer'
            },
            {
                name : '评分',
                href : '/enhance/rate'
            },
            {
                name : '颜色选择器',
                href : '/enhance/colorpicker'
            },
            {
                name : '日期',
                href : '/enhance/datepicker'
            },
            {
                name : '城市',
                href : '/enhance/citypicker'
            },
            {
                name : '树形',
                href : '/enhance/tree'
            },
            {
                name : '多级',
                href : '/enhance/cascade'
            },
            {
                name : '富文本编辑器',
                href : '/enhance/editor'
            },
            {
                name : '滑块',
                href : '/enhance/slider'
            },
            {
                name : '提及',
                href : '/enhance/mention'
            },
            {
                name : '拖拽',
                href : '/enhance/drag'
            },
            {
                name : '表单验证',
                href : '/enhance/validate'
            }
        ]
    },
    {
        name : '列表',
        href : 'javascript:;',
        icon : 'ri-list-check',
        children: [
            {
                name : '搜索',
                href : '/list/search'
            },
            {
                name : '分页',
                href : '/list/page'
            },
            {
                name : '表格',
                href : '/list/table'
            },
            {
                name : '自定义',
                href : '/list/custom'
            }
        ]
    },
    {
        name : '容器',
        href : 'javascript:;',
        icon : 'ri-archive-line',
        children: [
            {
                name : '弹窗',
                href : '/view/window'
            },
            {
                name : '选项卡',
                href : '/view/tab'
            },
            {
                name : '折叠面板',
                href : '/view/collapse'
            },
            {
                name : '看图器',
                href : '/view/imageview'
            },
            {
                name : '代码',
                href : '/view/code'
            },
            {
                name : '时间线',
                href : '/view/timeline'
            },
            {
                name : '空内容',
                href : '/view/empty'
            }
        ]
    },
    {
        name : '提醒',
        href : 'javascript:;',
        icon : 'ri-message-3-line',
        children: [
            {
                name : '警告',
                href : '/notice/alert'
            },
            {
                name : '消息',
                href : '/notice/message'
            },
            {
                name : '模态',
                href : '/notice/popup'
            },
            {
                name : '通知',
                href : '/notice/notice'
            }
        ]
    },
    {
        name : '图表',
        href : 'javascript:;',
        icon : 'ri-pie-chart-2-line',
        children: [
            {
                name : '柱状图',
                href : '/chart/bar'
            },
            {
                name : '折线图',
                href : '/chart/line'
            },
            {
                name : '饼状图',
                href : '/chart/pie'
            },
            {
                name : '气泡图',
                href : '/chart/bubble'
            },
            {
                name : '极地图',
                href : '/chart/polar'
            },
            {
                name : '雷达图',
                href : '/chart/radar'
            },
            {
                name : '综合演示',
                href : '/chart/all'
            }
        ]
    },
    {
        name : '常用',
        href : 'javascript:;',
        icon : 'ri-24-hours-line',
        children: [
            {
                name : '下拉菜单',
                href : '/common/dropdown'
            },
            {
                name : '状态',
                href : '/common/status'
            },
            {
                name : '数字',
                href : '/common/num'
            },
            {
                name : '标签',
                href : '/common/tag'
            },
            {
                name : 'Tips',
                href : '/common/tips'
            },
            {
                name : '进度条',
                href : '/common/progress'
            },
            {
                name : '复制',
                href : '/common/copy'
            },
            {
                name : '步骤',
                href : '/common/steps'
            },
            {
                name: '日历',
                href: '/common/calendar'
            }
        ]
    },
    {
        name : '模板',
        href : 'javascript:;',
        icon : 'ri-bill-line',
        children: [
            {
                name : '语法',
                href : '/tmp/tmp'
            }
        ]
    },
    {
        name : 'http',
        href : 'javascript:;',
        icon : 'ri-ie-line',
        children: [
            {
                name : '发送请求',
                href : '/http/request'
            }
        ]
    }
];