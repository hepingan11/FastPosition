import request from '@/utils/BSideRequest'


export function GetUserList(){
    return request({
        url: '/user/list',
        method: 'get',
    })
}