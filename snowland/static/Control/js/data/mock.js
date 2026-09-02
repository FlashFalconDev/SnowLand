/**
 * mock数据
 */

loader.ready(() => {

    // 登录
    // Mock.mock(/api\/login/, (options) => {
    //     let post = query(options.body, true);
    //     let code = 100;
    //     let msg  = '登入成功，頁面正在跳轉...';
    //     if (post.uname != 'eui')
    //     {
    //         code = 101;
    //         msg  = '帳號輸入錯誤';
    //     }
    //     else if (post.pword != '888888')
    //     {
    //         code = 101;
    //         msg  = '密碼輸入錯誤';
    //     }
    //     return {
    //         code   : code,
    //         msg    : msg,
    //         data   : {
    //             name : 'eui',
    //             icon : 'http://demo.eui6.com/static/img/icon.jpg',
    //             // 实际项目该值应该是后端计算后的JWT值
    //             jwt  : 1
    //         }
    //     };
    // });

    // 统一表示提交成功的模拟接口
    Mock.mock(/api\/success/, {
        code: 100,
        msg: '資料保存成功'
    });

    // 自动完成
    Mock.mock(/api\/autocomplete/, () => {
        let data = [];
        for (let i = 1; i < 16; i++)
        {
            data.push({
                name : `選單${i}`,
                id: i
            });
        }
        return {
            code : 100,
            data : {
                list : data
            }
        };
    });

    // 联动菜单子菜单数据
    Mock.mock(/api\/select/, (options) => {
        let get  = query(options.url, true);
        let data = {};
        if (get.fruit == 1)
        {
            data = {
                list : [
                    {
                        label : '苹果',
                        value : 1
                    },
                    {
                        label : '香蕉',
                        value : 2
                    },
                    {
                        label : '西瓜',
                        value : 3
                    },
                    {
                        label : '菠萝',
                        value : 4
                    },
                    {
                        label : '梨',
                        value : 5
                    },
                    {
                        label : '柚子',
                        value : 6
                    }
                ]
            };
        }
        else
        {
            data = {
                list : [
                    {
                        label : '足球',
                        value : 1
                    },
                    {
                        label : '篮球',
                        value : 2
                    },
                    {
                        label : '乒乓球',
                        value : 3
                    },
                    {
                        label : '羽毛球',
                        value : 4
                    }
                ]
            };
        }
        return {
            code : 100,
            data : data
        };
    });

    // 穿梭框
    Mock.mock(/api\/transfer/, () => {
        let data = [];
        for (var i = 1; i <= 10; i++)
        {
            data.push({
                // 显示的文本
                label : `${i == 5 ? 'eui' : '选项'}${i}`,
                // 真实取值
                value : i
            });
        }
        return {
            code : 100,
            data : {
                list: data
            }
        }
    });

    // 表格
    Mock.mock(/api\/table/, (options) => {
        let get  = query(options.url, true);
        get.size = get.size || 10;
        let list = [];
        for (var i = 1; i <= get.size; i++)
        {
            list.push({
                id      : i,
                order   : 0,
                emp     : `Eui - ${get.page}(${i})`,
                money   : (128 + i) + '.12',
                name    : '演示',
                icon    : '//demo.eui6.com/static/img/icon_1.jpg',
                pic     : '//demo.eui6.com/static/img/icon_2.jpg,//demo.eui6.com/static/img/icon_3.jpg,//demo.eui6.com/static/img/icon_4.jpg',
                area    : '上海',
                api     : '/api/table/',
                plan    : 1,
                tag     : 'js,css,vue',
                create  : 'Eui',
                addtime : 1628081989,
                audit   : 'admin',
                type    : 'GET',
                status  : 0,
                view    : 100 + i,
                use     : 88 - i,
                left    : (320 - i).toFixed(2)
            });
        }
        return {
            code : 100,
            msg  : '数据请求成功',
            data : {
                count: 100,
                list
            }
        }
    });

    // 表格汇总栏模拟
    Mock.mock(/api\/total/, {
        code: 100,
        data: {
            count: 100
        }
    });

    // 模拟分类数据
    Mock.mock(/api\/cate/, (options) => {
        const get = query(options.url, true);
        const list = {
            0 : [
                {
                    name: '男装',
                    id: 1
                },
                {
                    name: '女装',
                    id: 2
                },
                {
                    name: '童装',
                    id: 3
                }
            ],
            1 : [
                {
                    name: '上衣',
                    id: 1
                },
                {
                    name: '裤子',
                    id: 2
                },
                {
                    name: '鞋子',
                    id: 3
                }
            ],
            2 : [
                {
                    name: '帽子',
                    id: 1
                },
                {
                    name: '裙子',
                    id: 2
                },
                {
                    name: '手套',
                    id: 3
                }
            ],
            3 : [
                {
                    name: '童帽',
                    id: 1
                },
                {
                    name: '围巾',
                    id: 2
                },
                {
                    name: '棉鞋',
                    id: 3
                }
            ]
        };
        return {
            code: 100,
            msg: '数据请求成功',
            data: {
                list: list[get.cate || 0]
            }
        }
    });

    // 进度
    Mock.mock(/api\/progress/, () => {
        return {
            code : 100,
            msg  : '数据请求成功',
            data : {
                all : 100,
                num : 20
            }
        }
    });

    // get
    Mock.mock(/api\/get/, (options) => {
        let get = query(options.url, true);
        return {
            code : 100,
            msg  : 'GET请求执行成功',
            data : {
                type: options.type,
                query: get,
            }
        }
    });

    // post
    Mock.mock(/api\/post/, (options) => {
        let post = query(options.body, true);
        return {
            code : 100,
            msg  : `${options.type}请求执行成功`,
            data : {
                type : options.type,
                post : post
            }
        }
    });

    // 树形菜单子节点数据
    Mock.mock(/api\/childNode/, (options) => {
        let get  = query(options.url, true);
        let data = {};
        data['list'] = [];
        for (let i = 10; i < 20; i++)
        {
            data['list'].push({
                name     : `叶子节点：${get.id} - ${i}`,
                id       : `${i}${get.id}`,
                pid      : get.id,
                hasChild : 0
            });
        }
        return {
            code : 100,
            data : data
        };
    });

    // 远程校验
    Mock.mock(/api\/validate/, (options) => {
        let post = query(options.body, true);
        let code = 100;
        let msg  = '校验通过';
        if (post.uname !== 'eui')
        {
            code = 101;
            msg  = '该账户已经存在，无法注册';
        }
        return {
            code,
            msg
        };
    });

    // 提及
    Mock.mock(/api\/mention/, () => {
        let data = [];
        for (let i = 1; i <= 10; i++)
        {
            data.push({
                label : `eui-${i}`,
                value: i
            });
        }
        return {
            code : 100,
            data : {
                list : data
            }
        };
    });

    // 自定义分页演示数据
    Mock.mock(/api\/custom/, (options) => {
        let get  = query(options.url, true);
        get.page = get.page || 1;
        return {
            code: 100,
            data: {
                list: [
                    {
                        pic: '//p3.dcarimg.com/img/tos-cn-i-dcdx/60b8a92b0b304e60a4d0e8bc2f4f2272~332x0.webp',
                        name: `${get.page}-Model Y`,
                        price: '24.99-35.49万'
                    },
                    {
                        pic: '//p3.dcarimg.com/img/tos-cn-i-dcdx/7a507b6ec14c4ead9c95c336893aa9d2~332x0.webp',
                        name: `${get.page}-小米SU7`,
                        price: '21.59-29.99万'
                    },
                    {
                        pic: '//p3.dcarimg.com/img/tos-cn-i-dcdx/8c6e1943c2094ec2a14fd460d2c0ba4d~332x0.webp',
                        name: `${get.page}-ZEEKR 001`,
                        price: '25.90-32.90万'
                    },
                    {
                        pic: '//p3.dcarimg.com/img/tos-cn-i-dcdx/e547cdc3ae5c487e87a624378b76ab13~332x0.webp',
                        name: `${get.page}-Model 3`,
                        price: '13.99-19.79万'
                    },
                    {
                        pic: '//p3.dcarimg.com/img/tos-cn-i-dcdx/25d4d4c6e46f4f078d75e768fabd7f0e~332x0.webp',
                        name: `${get.page}-深蓝S07`,
                        price: '23.19-33.59万'
                    },
                    {
                        pic: '//p3.dcarimg.com/img/tos-cn-i-dcdx/57f96638e8d34ce282039ad70270aa98~332x0.webp',
                        name: `${get.page}-海鸥`,
                        price: '6.98-8.58万'
                    },
                    {
                        pic: '//p3.dcarimg.com/img/tos-cn-i-dcdx/c6eb4687b1d1477c86826edc4d417e6c~332x0.webp',
                        name: `${get.page}-问界M9`,
                        price: '46.98-56.98万'
                    },
                    {
                        pic: '//p3.dcarimg.com/img/tos-cn-i-dcdx/69adf783b37346dbae6000fff0502a9a~332x0.webp',
                        name: `${get.page}-宝马i3`,
                        price: '24.07-28.15万'
                    },
                    {
                        pic: '//p3.dcarimg.com/img/tos-cn-i-dcdx/0a5a6f5f1e4e417f823a51d894fa7345~332x0.webp',
                        name: `${get.page}-元PLUS`,
                        price: '11.98-14.78万'
                    },
                    {
                        pic: '//p3.dcarimg.com/img/tos-cn-i-dcdx/7a2cd16842634bdfa34c1169b8c02ee0~332x0.webp',
                        name: `${get.page}-宋L EV`,
                        price: '18.98-24.98万'
                    },
                    {
                        pic: '//p3.dcarimg.com/img/tos-cn-i-dcdx/e6d6f7c2291d47f6a4a7d19c3ec01892~332x0.webp',
                        name: `${get.page}-汉EV`,
                        price: '17.98-26.98万'
                    },
                    {
                        pic: '//p3.dcarimg.com/img/tos-cn-i-dcdx/89bf7774d79f44eab5d9acca6ba8712e~332x0.webp',
                        name: `${get.page}-深蓝SL03`,
                        price: '12.49-68.49万'
                    },
                    {
                        pic: '//p3.dcarimg.com/img/tos-cn-i-dcdx/4b38b8a6aaa5407a9f6c0bb5bc346058~332x0.webp',
                        name: `${get.page}-问界M5`,
                        price: '24.98-27.98万'
                    },
                    {
                        pic: '//p3.dcarimg.com/img/tos-cn-i-dcdx/2c5aa014fea141568f6df9bf6a486db0~332x0.webp',
                        name: `${get.page}-零跑C11`,
                        price: '12.78-20.33万'
                    },
                    {
                        pic: '//p3.dcarimg.com/img/tos-cn-i-dcdx/47aa2c230bd5475eabf82865b71fc484~332x0.webp',
                        name: `${get.page}-海豹`,
                        price: '17.58-24.98万'
                    },
                    {
                        pic: '//p3.dcarimg.com/img/tos-cn-i-dcdx/4f90467b59e54ad7a74c035d516e7772~332x0.webp',
                        name: `${get.page}-海豚`,
                        price: '9.39-12.58万'
                    },
                ]
            }
        };
    });

    // 演示无分页表格
    Mock.mock(/api\/newOrder/, () => {
        let list = [];
        for (var i = 1; i <= 8; i++)
        {
            list.push({
                id      : i,
                name    : 'eui开发手册',
                icon    : '//demo.eui6.com/static/img/icon_1.jpg',
                pic     : '//demo.eui6.com/static/img/icon_2.jpg,//demo.eui6.com/static/img/icon_3.jpg',
                pay     : 1,
                tag     : '男士,复购',
                have    : _.random(10, 90),
                price   : `¥${_.random(50, 500)}.00`,
                addtime : 1628081989
            });
        }
        return {
            code: 100,
            msg: '数据请求成功',
            data: {
                list
            }
        }
    });

});