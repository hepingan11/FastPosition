import request from '@/utils/BSideRequest'

export function getCompanyLinks(params) {
    return request({
        url: '/company-links',
        method: 'get',
        params
    })
}

export function getCompanyLink(id) {
    return request({
        url: `/company-links/${id}`,
        method: 'get'
    })
}

export function createCompanyLink(data) {
    return request({
        url: '/company-links',
        method: 'post',
        data
    })
}

export function updateCompanyLink(id, data) {
    return request({
        url: `/company-links/${id}`,
        method: 'put',
        data
    })
}

export function deleteCompanyLink(id) {
    return request({
        url: `/company-links/${id}`,
        method: 'delete'
    })
}

export function batchCrawlCompanyLinks(companyLinkIds) {
    return request({
        url: '/company-links/batch-crawl',
        method: 'post',
        data: {
            company_link_ids: companyLinkIds
        }
    })
}

export function startBatchCrawlCompanyLinks(companyLinkIds) {
    return request({
        url: '/company-links/batch-crawl/start',
        method: 'post',
        data: {
            company_link_ids: companyLinkIds
        }
    })
}

export function getBatchCrawlTaskStatus(taskId) {
    return request({
        url: `/company-links/batch-crawl/${taskId}`,
        method: 'get'
    })
}
