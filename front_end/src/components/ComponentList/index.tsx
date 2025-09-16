import React from 'react';
import { List, Tag } from 'antd';
import { Component } from '../../services/types';
import './style.css';

interface Props {
    components: Component[];
}

const ComponentList: React.FC<Props> = ({ components }) => {
    return (
    <List
        className="component-list"
        itemLayout="horizontal"
        dataSource={components}
        renderItem={item => (
        <List.Item>
            <List.Item.Meta
            title={item.title}
            description={item.Justification}
            />
            <Tag color={
            item.status === 'passed' ? 'green' : 
            item.status === 'discarded' ? 'red' : 'gold'
            }>
            {item.status || 'to be confirmed'}
            </Tag>
        </List.Item>
        )}
    />
    );
};

export default ComponentList;