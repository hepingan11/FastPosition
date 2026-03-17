import request from '@/utils/BSideRequest'

export function getPositions(params) {
    return request({
        url: '/positions',
        method: 'get',
        params
    })
}

export function getPositionById(id) {
    return request({
        url: `/positions/${id}`,
        method: 'get'
    })
}

export function recommendPositions(resumeId) {
    return request({
        url: `/positions/recommend/${resumeId}`,
        method: 'get'
    })
}
