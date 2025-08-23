<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class PermissionPermissionType extends Model
{
    use HasFactory, SoftDeletes;
    protected $table = 'permission_permission_types';
    
    protected $fillable = [
        'id',
        'permission_type_id',
        'permission_id',
        'status',       
        'created_at',
        'updated_at',
        'role_id',
        'deleted_at'
    ];

    public function getpermissionType() {
        return $this->hasMany(PermissionType::class,'id','permission_type_id')
        ->select('permission_types.*');
    } 

    public function getPermission() {
        return $this->hasMany(Permission::class,'id','permission_id')
        ->select('permissions.*');
    }
}
