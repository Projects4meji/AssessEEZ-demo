<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class IqaReport extends Model
{
    use HasFactory, SoftDeletes;

    protected $fillable = [
        'id',
        'date',
        'title',
        'qualification_id',
        'assessor_id',
        'learner_id',
        'attachement',
        'status',
        'created_by',
        'updated_by',
        'created_at',
        'updated_at',
        'deleted_at'
    ];
}
